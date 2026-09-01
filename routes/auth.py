import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from utils.db import get_db

bp = Blueprint("auth", __name__)

@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        row = db.execute("SELECT * FROM administrators WHERE username=?", (username,)).fetchone()
        if row and row["locked_until"]:
            try:
                locked = datetime.datetime.fromisoformat(row["locked_until"])
                if datetime.datetime.utcnow() < locked:
                    flash("Account temporarily locked. Try again later.", "danger")
                    return render_template("admin/login.html"), 403
            except:
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
                    locked_until = (datetime.datetime.utcnow() + datetime.timedelta(minutes=15)).isoformat()
                db.execute("UPDATE administrators SET failed_attempts=?, locked_until=? WHERE id=?", (fails, locked_until, row["id"]))
                db.commit()
            flash("Invalid username or password.", "danger")
            return render_template("admin/login.html"), 401
    return render_template("admin/login.html")

@bp.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("auth.admin_login"))
