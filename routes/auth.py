import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from utils.db import get_db
from utils.ratelimit import limiter

bp = Blueprint("auth", __name__)

# Canonical login path is /admin/login and is PUBLIC by design (see GH issue #3:
# obscurity is not a control — the path already leaks via redirects, HTML, JS,
# and git history). The legacy obscure path stays as a byte-identical alias on
# the same view so old bookmarks keep working. Decorator order matters:
# /admin/login is registered first so url_for("auth.admin_login") resolves to it.
@bp.route("/hanapanngbaddieguardsimarkus", methods=["GET", "POST"])
@bp.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        row = db.execute("SELECT * FROM administrators WHERE username=?", (username,)).fetchone()
        if row and row["locked_until"]:
            try:
                locked = datetime.datetime.fromisoformat(row["locked_until"])
                if locked.tzinfo is None:
                    locked = locked.replace(tzinfo=datetime.timezone.utc)
                if datetime.datetime.now(datetime.timezone.utc) < locked:
                    # Generic wording, no username echo: a locked account inherently
                    # confirms the name exists (residual oracle, GH #3 TM-002), so
                    # say as little as possible. 429 (not 403) — this is rate
                    # control, and 403-vs-401 would be a cleaner oracle signal.
                    flash("Too many failed attempts. Try again later.", "danger")
                    return render_template("admin/login.html"), 429
            except Exception:
                pass
        if row and check_password_hash(row["password_hash"], password):
            db.execute("UPDATE administrators SET failed_attempts=0, locked_until=NULL, last_login=datetime('now') WHERE id=?", (row["id"],))
            db.commit()
            session.clear()
            session["admin_id"] = row["id"]
            session["username"] = row["username"]
            session.permanent = True
            return redirect(url_for("admin.dashboard"))
        else:
            if row:
                fails = (row["failed_attempts"] or 0) + 1
                locked_until = None
                if fails >= 5:
                    # Hard 15-min lockout on a single-admin app is a known
                    # lockout-DoS vector (GH #3 TM-003): anyone who knows the
                    # username can blind the admin. Kept because the mechanics
                    # are pinned by tests and proportionate for this deployment;
                    # revisit with backoff/CAPTCHA if admin DoS is observed.
                    # NOTE: limiter uses memory:// storage — under multi-worker
                    # gunicorn each worker counts separately (limit x workers).
                    locked_until = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).isoformat()
                db.execute("UPDATE administrators SET failed_attempts=?, locked_until=? WHERE id=?", (fails, locked_until, row["id"]))
                db.commit()
            flash("Invalid username or password.", "danger")
            return render_template("admin/login.html"), 401
    return render_template("admin/login.html")

@bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("auth.admin_login"))
