import os
import time
import datetime as _dt
from collections import deque
from pathlib import Path
import click
from flask import Flask, render_template, g, request
from dotenv import load_dotenv

load_dotenv()

# Process boot time — exposed via /api/status as build_id so clients can
# invalidate stale offline caches after a server restart/update.
STARTED_AT = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

from config import config_by_name
from utils.db import get_db, close_db, init_db
from utils.seed import seed_db

def create_app(env=None):
    if env is None:
        env = os.getenv("FLASK_ENV", "development")
        cfg_name = "production" if env == "production" else "testing" if env == "testing" else "development"
    else:
        cfg_name = env

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[cfg_name])
    # Validate production secrets eagerly — fail loud if SECRET_KEY not set
    if cfg_name == "production":
        config_by_name[cfg_name].validate()
    app.config["ADMIN_USERNAME"] = os.getenv("ADMIN_USERNAME", "admin")
    app.config["ADMIN_PASSWORD"] = os.getenv("ADMIN_PASSWORD", "admin123")
    app.config["OPENWEATHER_API_KEY"] = os.getenv("OPENWEATHER_API_KEY", app.config.get("OPENWEATHER_API_KEY",""))
    app.config["FIRMS_MAP_KEY"] = os.getenv("FIRMS_MAP_KEY", app.config.get("FIRMS_MAP_KEY", ""))
    app.config["MAPBOX_TOKEN"] = os.getenv("MAPBOX_TOKEN", app.config.get("MAPBOX_TOKEN", ""))
    app.config["STARTED_AT"] = STARTED_AT

    # Cache-bust every static asset with the server boot timestamp. Browsers
    # heuristic-cache static files aggressively (the no-cache headers only
    # cover HTML/JSON), so a stale cached CSS/JS is the #1 cause of "still
    # shows the old version". The suffix changes on every restart, forcing
    # fresh static files with no manual ?v= bumping.
    @app.template_global()
    def static_asset(filename):
        from flask import url_for as _url_for
        return _url_for("static", filename=filename) + "?v=" + STARTED_AT
    if cfg_name == "testing":
        # A developer .env key must not leak into the suite: tests such as
        # test_api_weather_no_cache_503 expect a 503 when providers fail.
        app.config["OPENWEATHER_API_KEY"] = ""
        # Same for FIRMS: test_fires_requires_key expects 503 with no key.
        app.config["FIRMS_MAP_KEY"] = ""

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    # Extensions
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)

    try:
        from utils.ratelimit import limiter as shared_limiter
        shared_limiter.init_app(app)
        app.limiter = shared_limiter
    except Exception as e:
        app.logger.warning("Flask-Limiter init failed: %s", e)
        app.limiter = None

    app.teardown_appcontext(close_db)

    # Self-heal stale DB files: SCHEMA is all CREATE TABLE/INDEX IF NOT
    # EXISTS, so this safely adds tables missing from DBs created before a
    # feature landed (e.g. announcements) without touching existing data.
    # Skipped for :memory: (tests manage their own lifecycle).
    if app.config["DATABASE"] != ":memory:":
        try:
            with app.app_context():
                init_db()
                # Ephemeral disks (Render free tier) boot with an empty DB after
                # every deploy/restart — seed demo data when no centers exist yet.
                # seed_db() only fills empty tables, so this is a no-op otherwise.
                row = get_db().execute("SELECT COUNT(*) AS n FROM evacuation_centers").fetchone()
                if (row["n"] if row else 0) == 0:
                    seed_db()
                # Bulk dataset: data/ncr_evacuation_centers.geojson ships with
                # the repo but the import is a manual CLI step — ephemeral
                # hosts (Render free tier) would otherwise serve only the 20
                # demo rows forever. Auto-import once: the importer is
                # idempotent, so this is a no-op when rows already exist.
                try:
                    from scripts.import_evac_centers import import_geojson, DEFAULT_PATH
                    have = get_db().execute(
                        "SELECT COUNT(*) AS n FROM evacuation_centers "
                        "WHERE source LIKE 'geojson:%'").fetchone()
                    if (have["n"] if have else 0) == 0 and DEFAULT_PATH.exists():
                        stats = import_geojson(get_db(), str(DEFAULT_PATH))
                        app.logger.info("GeoJSON auto-import: %s", stats)
                except Exception as ie:
                    app.logger.warning("GeoJSON auto-import skipped: %s", ie)
        except Exception as e:
            app.logger.warning("Schema ensure failed for %s: %s", app.config["DATABASE"], e)

    # CLI
    @app.cli.command("init-db")
    def init_db_cmd():
        with app.app_context():
            init_db()
            print("Database initialized at", app.config["DATABASE"])

    @app.cli.command("seed")
    def seed_cmd():
        with app.app_context():
            init_db()
            seed_db()
            print("Database seeded.")

    @app.cli.command("import-geojson")
    @click.argument("path", required=False)
    def import_geojson_cmd(path=None):
        """Sprint 2: load data/ncr_evacuation_centers.geojson (idempotent)."""
        import json as _json
        from scripts.import_evac_centers import import_geojson, DEFAULT_PATH
        src = path or str(DEFAULT_PATH)
        with app.app_context():
            stats = import_geojson(get_db(), src)
            print(_json.dumps(stats, indent=2))

    # Blueprints — organized routes/
    from routes.public import bp as public_bp
    from routes.auth import bp as auth_bp
    from routes.admin import bp as admin_bp
    from routes.api import bp as api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # CSRF exempt APIs
    try:
        csrf.exempt(api_bp)
    except Exception as e:
        app.logger.warning("CSRF exempt failed: %s", e)

    # Lightweight analytics: per-request timing (in-memory rolling sample)
    # plus a persistent visits log (endpoint only — no IPs, no user agents).
    # Static assets are excluded so CSS/JS fetches don't inflate counts.
    if not hasattr(app, "perf_samples"):
        app.perf_samples = deque(maxlen=500)
        app.req_count = 0
        app.err_count = 0

    @app.before_request
    def _perf_start():
        g._t0 = time.perf_counter()

    @app.after_request
    def track_visit(resp):
        try:
            t0 = g.pop("_t0", None)
            if t0 is not None:
                app.perf_samples.append((time.perf_counter() - t0) * 1000)
            app.req_count += 1
            if resp.status_code >= 500:
                app.err_count += 1
            ep = request.endpoint or ""
            if ep and ep != "static":
                db = get_db()
                db.execute("INSERT INTO visits (endpoint) VALUES (?)", (ep,))
                db.execute("DELETE FROM visits WHERE ts < datetime('now', '-30 days')")
                db.commit()
        except Exception:
            app.logger.debug("visit tracking skipped", exc_info=True)
        return resp

    # Kill stale-page syndrome: phone browsers aggressively heuristic-cache
    # HTML/JSON (no validators sent), hiding new tabs like Group/Routes.
    # Static assets keep their own cache headers — only dynamic responses.
    @app.after_request
    def no_cache_dynamic(resp):
        if (resp.mimetype or "").startswith(("text/html", "application/json")):
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        return resp

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e): return render_template("errors/400.html"), 400
    @app.errorhandler(401)
    def unauthorized(e): return render_template("errors/401.html"), 401
    @app.errorhandler(403)
    def forbidden(e): return render_template("errors/403.html"), 403
    @app.errorhandler(404)
    def not_found(e): return render_template("errors/404.html"), 404
    @app.errorhandler(500)
    def server_error(e): return render_template("errors/500.html"), 500

    return app

# For gunicorn / flask run
app = create_app()
