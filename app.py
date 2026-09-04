import os
from pathlib import Path
from flask import Flask, render_template
from dotenv import load_dotenv

load_dotenv()

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
    if cfg_name == "testing":
        # A developer .env key must not leak into the suite: tests such as
        # test_api_weather_no_cache_503 expect a 503 when providers fail.
        app.config["OPENWEATHER_API_KEY"] = ""

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
