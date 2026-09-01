from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Please log in to access admin.", "warning")
            return redirect(url_for("auth.admin_login"))
        return f(*args, **kwargs)
    return wrap
