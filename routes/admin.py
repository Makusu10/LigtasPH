from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db import get_db
from utils.security import login_required
from utils.validators import validate_phone

bp = Blueprint("admin", __name__)

SUPPLY_ENUM = ("Unknown", "Low", "Adequate", "High")
OPERATIONAL_ENUM = ("Open", "Closed", "Temporarily Unavailable")
HOTLINE_CATEGORIES = ("National", "DRRMO", "Police", "Fire", "Medical", "Rescue", "Hospital", "Utility")

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
    return render_template("admin/hotlines.html", hotlines=hotlines, categories=HOTLINE_CATEGORIES)


def _parse_announcement_form(form):
    import datetime as _dt
    title = (form.get("title") or "").strip()[:120]
    message = (form.get("message") or "").strip()[:2000]
    scope = (form.get("scope") or "all").strip()
    city = (form.get("city") or "").strip()[:80]
    severity = (form.get("severity") or "info").strip()
    starts_raw = (form.get("starts_at") or "").strip()
    ends_raw = (form.get("ends_at") or "").strip()
    errors = []
    if not title:
        errors.append("Title is required.")
    if not message:
        errors.append("Message is required.")
    if scope not in ("all", "city", "radius"):
        errors.append("Scope must be all, city, or radius.")
    if severity not in ("info", "warning", "critical"):
        severity = "info"
    if scope == "city" and not city:
        errors.append("City is required for city-scoped announcements.")
    center_lat = center_lng = radius_km = None
    if scope == "radius":
        try:
            center_lat = float(form.get("center_lat"))
            center_lng = float(form.get("center_lng"))
            radius_km = float(form.get("radius_km"))
            if not (-90 <= center_lat <= 90 and -180 <= center_lng <= 180):
                errors.append("Invalid center coordinates.")
            if not (0 < radius_km <= 2000):
                errors.append("Radius must be 1–2000 km.")
        except (TypeError, ValueError):
            errors.append("Center lat/lng and radius are required for radius scope.")
    # datetime-local "YYYY-MM-DDTHH:MM" -> "YYYY-MM-DD HH:MM:00" (UTC-naive, compared via datetime())
    def _norm(v):
        v = (v or "").strip().replace("T", " ")[:16]
        if len(v) == 16:
            v += ":00"
        return v
    starts_at, ends_at = _norm(starts_raw), _norm(ends_raw)
    try:
        s = _dt.datetime.strptime(starts_at, "%Y-%m-%d %H:%M:%S")
        e = _dt.datetime.strptime(ends_at, "%Y-%m-%d %H:%M:%S")
        if not s < e:
            errors.append("End time must be after start time.")
    except ValueError:
        errors.append("Start and end times are required (valid date/time).")
    return {
        "title": title, "message": message, "scope": scope,
        "city": city if scope == "city" else "",
        "center_lat": center_lat if scope == "radius" else None,
        "center_lng": center_lng if scope == "radius" else None,
        "radius_km": radius_km if scope == "radius" else None,
        "severity": severity, "starts_at": starts_at, "ends_at": ends_at,
    }, errors


@bp.route("/admin/announcements", methods=["GET", "POST"])
@login_required
def announcements():
    db = get_db()
    if request.method == "POST":
        data, errors = _parse_announcement_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            db.execute(
                """INSERT INTO announcements
                   (title, message, scope, city, center_lat, center_lng, radius_km,
                    severity, starts_at, ends_at, created_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (data["title"], data["message"], data["scope"], data["city"],
                 data["center_lat"], data["center_lng"], data["radius_km"],
                 data["severity"], data["starts_at"], data["ends_at"],
                 session.get("admin_id")),
            )
            db.commit()
            flash("Announcement published.", "success")
            return redirect(url_for("admin.announcements"))
    rows = db.execute("SELECT * FROM announcements ORDER BY starts_at DESC").fetchall()
    cities = db.execute(
        "SELECT DISTINCT city FROM evacuation_centers WHERE archived=0 ORDER BY city"
    ).fetchall()
    return render_template("admin/announcements.html", announcements=rows, cities=cities)


@bp.route("/admin/announcements/<int:aid>/toggle", methods=["POST"])
@login_required
def announcement_toggle(aid):
    db = get_db()
    row = db.execute("SELECT id, is_active FROM announcements WHERE id=?", (aid,)).fetchone()
    if not row:
        flash("Announcement not found.", "danger")
    else:
        db.execute("UPDATE announcements SET is_active=? WHERE id=?",
                   (0 if row["is_active"] else 1, aid))
        db.commit()
        flash("Announcement disabled." if row["is_active"] else "Announcement enabled.", "success")
    return redirect(url_for("admin.announcements"))


@bp.route("/admin/announcements/<int:aid>/delete", methods=["POST"])
@login_required
def announcement_delete(aid):
    db = get_db()
    db.execute("DELETE FROM announcements WHERE id=?", (aid,))
    db.commit()
    flash("Announcement deleted.", "info")
    return redirect(url_for("admin.announcements"))

@bp.route("/admin/centers/<int:cid>", methods=["POST"])
@login_required
def update_center(cid):
    db = get_db()
    c = db.execute("SELECT * FROM evacuation_centers WHERE id=?", (cid,)).fetchone()
    if not c:
        flash("Center not found.", "danger")
        return redirect(url_for("admin.centers")), 404
    try:
        occupancy = int(request.form.get("current_occupancy", c["current_occupancy"]))
    except (TypeError, ValueError):
        flash("Occupancy must be a whole number.", "danger")
        return redirect(url_for("admin.centers")), 400
    if not (0 <= occupancy <= c["capacity"]):
        flash(f"Occupancy must be 0–{c['capacity']}.", "danger")
        return redirect(url_for("admin.centers")), 400
    supplies = {}
    for field in ("food_status", "water_status", "medicine_status", "hygiene_status", "basic_needs_status"):
        val = request.form.get(field, c[field])
        if val not in SUPPLY_ENUM:
            flash(f"Invalid {field}.", "danger")
            return redirect(url_for("admin.centers")), 400
        supplies[field] = val
    operational = request.form.get("operational_status", c["operational_status"])
    if operational not in OPERATIONAL_ENUM:
        flash("Invalid operational status.", "danger")
        return redirect(url_for("admin.centers")), 400
    contact = request.form.get("contact_number", c["contact_number"] or "").strip()[:20]
    if contact and not validate_phone(contact):
        flash("Invalid contact number.", "danger")
        return redirect(url_for("admin.centers")), 400
    notes = request.form.get("notes", c["notes"] or "").strip()[:2000]
    db.execute(
        """UPDATE evacuation_centers SET current_occupancy=?, food_status=?, water_status=?,
           medicine_status=?, hygiene_status=?, basic_needs_status=?, operational_status=?,
           contact_number=?, notes=?, updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=?""",
        (occupancy, supplies["food_status"], supplies["water_status"], supplies["medicine_status"],
         supplies["hygiene_status"], supplies["basic_needs_status"], operational, contact or None, notes or None, cid),
    )
    db.execute(
        """INSERT INTO center_status_updates (center_id, prev_occupancy, new_occupancy, food_status,
           water_status, medicine_status, hygiene_status, basic_needs_status, notes, admin_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (cid, c["current_occupancy"], occupancy, supplies["food_status"], supplies["water_status"],
         supplies["medicine_status"], supplies["hygiene_status"], supplies["basic_needs_status"],
         notes or None, session.get("admin_id")),
    )
    db.commit()
    flash("Center updated.", "info")
    return redirect(url_for("admin.centers"))

@bp.route("/admin/centers/<int:cid>/archive", methods=["POST"])
@login_required
def archive_center(cid):
    db = get_db()
    action = (request.form.get("action", "archive") or "archive").strip()
    archived = 0 if action == "unarchive" else 1
    cur = db.execute("UPDATE evacuation_centers SET archived=?, updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=?", (archived, cid))
    db.commit()
    if cur.rowcount == 0:
        flash("Center not found.", "danger")
        return redirect(url_for("admin.centers")), 404
    flash("Center archived." if archived else "Center restored.", "info")
    return redirect(url_for("admin.centers"))

@bp.route("/admin/hotlines", methods=["POST"])
@login_required
def create_hotline():
    db = get_db()
    agency = (request.form.get("agency", "") or "").strip()[:120]
    category = (request.form.get("category", "") or "").strip()
    contact = (request.form.get("contact_number", "") or "").strip()[:20]
    city = (request.form.get("city", "") or "").strip()[:80]
    if not agency or not contact or not city:
        flash("Agency, number, and city are required.", "danger")
        return redirect(url_for("admin.hotlines")), 400
    if category not in HOTLINE_CATEGORIES:
        flash("Invalid category.", "danger")
        return redirect(url_for("admin.hotlines")), 400
    if not validate_phone(contact):
        flash("Invalid contact number.", "danger")
        return redirect(url_for("admin.hotlines")), 400
    db.execute(
        "INSERT INTO emergency_hotlines (agency, category, contact_number, city, last_verified) VALUES (?,?,?,?,date('now'))",
        (agency, category, contact, city),
    )
    db.commit()
    flash("Hotline added.", "info")
    return redirect(url_for("admin.hotlines")), 201

@bp.route("/admin/hotlines/<int:hid>/archive", methods=["POST"])
@login_required
def archive_hotline(hid):
    db = get_db()
    action = (request.form.get("action", "archive") or "archive").strip()
    archived = 0 if action == "unarchive" else 1
    cur = db.execute("UPDATE emergency_hotlines SET archived=?, updated_at=datetime('now') WHERE id=?", (archived, hid))
    db.commit()
    if cur.rowcount == 0:
        flash("Hotline not found.", "danger")
        return redirect(url_for("admin.hotlines")), 404
    flash("Hotline archived." if archived else "Hotline restored.", "info")
    return redirect(url_for("admin.hotlines"))
