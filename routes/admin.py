from flask import Blueprint, render_template
from utils.db import get_db
from utils.security import login_required

bp = Blueprint("admin", __name__)

@bp.route("/admin/dashboard")
@login_required
def dashboard():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM evacuation_centers WHERE archived=0").fetchone()["c"]
    centers = db.execute("SELECT * FROM evacuation_centers WHERE archived=0").fetchall()
    total_capacity = sum(c["capacity"] for c in centers)
    total_occ = sum(c["current_occupancy"] for c in centers)
    available = nearly = full = low_supply = 0
    for c in centers:
        pct = c["current_occupancy"]/c["capacity"]*100 if c["capacity"] else 0
        if pct >=100: full+=1
        elif pct>=80: nearly+=1
        else: available+=1
        if c["food_status"] in ("Low",) or c["water_status"] in ("Low",) or c["medicine_status"] in ("Low",):
            low_supply+=1
    recent = db.execute("SELECT * FROM evacuation_centers WHERE archived=0 ORDER BY updated_at DESC LIMIT 5").fetchall()
    stale = db.execute("SELECT * FROM evacuation_centers WHERE archived=0 AND julianday('now') - julianday(updated_at) > 7 ORDER BY updated_at ASC LIMIT 5").fetchall()
    return render_template("admin/dashboard.html", total=total, available=available, nearly=nearly, full=full, total_capacity=total_capacity, total_occ=total_occ, low_supply=low_supply, recent=recent, stale=stale)

@bp.route("/admin/centers")
@login_required
def centers():
    db = get_db()
    centers = db.execute("SELECT * FROM evacuation_centers ORDER BY updated_at DESC").fetchall()
    return render_template("admin/centers.html", centers=centers)

@bp.route("/admin/hotlines")
@login_required
def hotlines():
    db = get_db()
    hotlines = db.execute("SELECT * FROM emergency_hotlines ORDER BY updated_at DESC").fetchall()
    return render_template("admin/hotlines.html", hotlines=hotlines)
