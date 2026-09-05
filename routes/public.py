from flask import Blueprint, render_template, current_app, send_from_directory
from utils.db import get_db

bp = Blueprint("public", __name__)

@bp.route("/")
def home():
    db = get_db()
    rows = db.execute("SELECT COUNT(*) c FROM evacuation_centers WHERE archived=0").fetchone()
    total = rows["c"] if rows else 0
    centers = db.execute("SELECT * FROM evacuation_centers WHERE archived=0 ORDER BY updated_at DESC").fetchall()
    available = nearly = full = unknown = 0
    for c in centers:
        if c["capacity"] is None or c["current_occupancy"] is None:
            # Sprint 2 imports without admin-set numbers: never counted as Available.
            unknown += 1
            continue
        pct = (c["current_occupancy"] / c["capacity"] * 100) if c["capacity"] else 0
        if pct >= 100:
            full += 1
        elif pct >= 80:
            nearly += 1
        else:
            available += 1
    recent = db.execute("SELECT * FROM evacuation_centers WHERE archived=0 ORDER BY updated_at DESC LIMIT 4").fetchall()
    last_updated = db.execute("SELECT MAX(updated_at) as m FROM evacuation_centers").fetchone()
    return render_template("public/home.html", total=total, available=available, nearly=nearly, full=full, unknown=unknown, centers=recent, last_updated=last_updated["m"] if last_updated else None, is_demo=current_app.config.get("IS_DEMO", True), mapbox_token=current_app.config.get("MAPBOX_TOKEN", ""))

@bp.route("/map")
def map_page():
    return render_template("public/map.html", mapbox_token=current_app.config.get("MAPBOX_TOKEN", ""))

@bp.route("/sw.js")
def service_worker():
    """Offline-resilience Service Worker (map page). Served from static so the
    SW can be updated by simply replacing static/js/sw.js."""
    return send_from_directory(current_app.static_folder, "js/sw.js", mimetype="application/javascript")

@bp.route("/centers")
def centers_page():
    return render_template("public/directory.html")

@bp.route("/centers/<int:center_id>")
def center_detail(center_id):
    db = get_db()
    c = db.execute("SELECT * FROM evacuation_centers WHERE id=? AND archived=0", (center_id,)).fetchone()
    if not c:
        return render_template("errors/404.html"), 404
    if c["capacity"] is None or c["current_occupancy"] is None:
        pct = avail = None
        status = "Status Unavailable"
    else:
        pct = round(c["current_occupancy"]/c["capacity"]*100,1) if c["capacity"] else 0
        avail = c["capacity"] - c["current_occupancy"]
        status = "Full" if pct>=100 else "Nearly Full" if pct>=80 else "Available" if c["operational_status"]=="Open" else "Status Unavailable"
    return render_template("public/center_detail.html", c=c, pct=pct, avail=avail, status=status, mapbox_token=current_app.config.get("MAPBOX_TOKEN", ""))

@bp.route("/weather")
def weather_page():
    return render_template("public/weather.html")

@bp.route("/hotlines")
def hotlines_page():
    return render_template("public/hotlines.html")

@bp.route("/settings")
def settings_page():
    return render_template("public/settings.html")
