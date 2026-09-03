from flask import Blueprint, request, jsonify
from utils.db import get_db

bp = Blueprint("api", __name__)

import secrets
import sqlite3
import string

_INVITE_ALPHABET = string.ascii_uppercase + string.digits


def _new_invite_code(n=6):
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(n))

@bp.route("/api/centers")
def api_centers():
    db = get_db()
    q = request.args.get("q","").strip()
    city = request.args.get("city","").strip()
    status = request.args.get("status","").strip()
    supply = request.args.get("supply","").strip()
    sort = request.args.get("sort","updated")
    sql = "SELECT * FROM evacuation_centers WHERE archived=0"
    params=[]
    if q:
        sql += " AND (name LIKE ? OR city LIKE ? OR address LIKE ?)"
        like = f"%{q}%"
        params.extend([like,like,like])
    if city:
        sql += " AND city=?"
        params.append(city)
    centers = db.execute(sql, params).fetchall()
    out=[]
    for c in centers:
        d=dict(c)
        pct = round(c["current_occupancy"]/c["capacity"]*100,1) if c["capacity"] else 0
        avail = c["capacity"] - c["current_occupancy"]
        occ_status = "Full" if pct>=100 else "Nearly Full" if pct>=80 else "Available" if c["operational_status"]=="Open" else "Status Unavailable"
        d["occupancy_pct"]=pct; d["available_slots"]=avail; d["occupancy_status"]=occ_status
        if supply and supply not in (c["food_status"], c["water_status"], c["medicine_status"], c["hygiene_status"], c["basic_needs_status"]):
            continue
        if status and occ_status!=status:
            continue
        out.append(d)
    if sort=="name":
        out.sort(key=lambda x: x["name"].lower())
    elif sort=="available":
        out.sort(key=lambda x: x["available_slots"], reverse=True)
    elif sort=="occupancy":
        out.sort(key=lambda x: x["occupancy_pct"], reverse=True)
    else:
        out.sort(key=lambda x: x["updated_at"], reverse=True)
    return jsonify(out)

@bp.route("/api/centers/<int:cid>")
def api_center_detail(cid):
    db=get_db()
    c=db.execute("SELECT * FROM evacuation_centers WHERE id=? AND archived=0", (cid,)).fetchone()
    if not c: return jsonify({"error":"Not found"}),404
    d=dict(c)
    pct= round(c["current_occupancy"]/c["capacity"]*100,1) if c["capacity"] else 0
    d["occupancy_pct"]=pct; d["available_slots"]=c["capacity"]-c["current_occupancy"]
    d["occupancy_status"]="Full" if pct>=100 else "Nearly Full" if pct>=80 else "Available" if c["operational_status"]=="Open" else "Status Unavailable"
    return jsonify(d)

@bp.route("/api/hotlines")
def api_hotlines():
    db=get_db()
    city=request.args.get("city","").strip()
    category=request.args.get("category","").strip()
    q=request.args.get("q","").strip()
    sql="SELECT * FROM emergency_hotlines WHERE archived=0"
    params=[]
    if city and city!="All":
        sql+=" AND (city=? OR city='National')"
        params.append(city)
    if category:
        sql+=" AND category=?"
        params.append(category)
    if q:
        sql+=" AND (agency LIKE ? OR contact_number LIKE ? OR address_area LIKE ?)"
        like=f"%{q}%"
        params.extend([like,like,like])
    sql+=" ORDER BY last_verified DESC, updated_at DESC"
    rows=db.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])

@bp.route("/api/weather")
def api_weather():
    try:
        from services.weather_service import fetch_weather
        db=get_db()
        lat=request.args.get("lat", "14.6308")
        lon=request.args.get("lon", "121.0968")
        city=request.args.get("city")
        try:
            lat_f=float(lat); lon_f=float(lon)
            if not (-90<=lat_f<=90 and -180<=lon_f<=180):
                return jsonify({"error":"Invalid coordinates"}),400
        except (TypeError, ValueError):
            return jsonify({"error":"Invalid coordinates"}),400
        data, err = fetch_weather(db, lat_f, lon_f, city)
        if data:
            return jsonify(data)
        return jsonify({"error": err or "Weather unavailable", "retry": True}), 503
    except Exception:
        return jsonify({"error":"Weather unavailable", "retry": True}), 503

@bp.route("/api/air-quality")
def api_air_quality():
    try:
        from services.air_quality_service import fetch_air_quality
        db=get_db()
        lat=request.args.get("lat", "14.6308")
        lon=request.args.get("lon", "121.0968")
        city=request.args.get("city")
        try:
            lat_f=float(lat); lon_f=float(lon)
            if not (-90<=lat_f<=90 and -180<=lon_f<=180):
                return jsonify({"error":"Invalid coordinates"}),400
        except (TypeError, ValueError):
            return jsonify({"error":"Invalid coordinates"}),400
        data, err = fetch_air_quality(db, lat_f, lon_f, city)
        if data:
            return jsonify(data)
        return jsonify({"error": err or "Air quality unavailable", "retry": True}), 503
    except Exception:
        return jsonify({"error":"Air quality unavailable", "retry": True}), 503

@bp.route("/api/environment")
def api_environment():
    try:
        from services.weather_service import fetch_weather
        from services.air_quality_service import fetch_air_quality
        from utils.environment import overall_status
        db=get_db()
        lat=request.args.get("lat", "14.6308")
        lon=request.args.get("lon", "121.0968")
        city=request.args.get("city")
        try:
            lat_f=float(lat); lon_f=float(lon)
            if not (-90<=lat_f<=90 and -180<=lon_f<=180):
                return jsonify({"error":"Invalid coordinates"}),400
        except (TypeError, ValueError):
            return jsonify({"error":"Invalid coordinates"}),400
        w_data, w_err = fetch_weather(db, lat_f, lon_f, city)
        aq_data, aq_err = fetch_air_quality(db, lat_f, lon_f, city)
        # Do not fabricate — return what we have, unavailable otherwise
        heat_cat = (w_data or {}).get("heat_index", {}).get("category") if w_data else None
        aqi_cat = (aq_data or {}).get("category") if aq_data else None
        overall = overall_status(heat_cat, aqi_cat)
        # Shared coords + source stamps
        return jsonify({
            "weather": w_data,
            "air_quality": aq_data,
            "overall": overall,
            "errors": {"weather": w_err, "air_quality": aq_err},
        })
    except Exception as e:
        return jsonify({"error":"Environment data unavailable", "retry": True}), 503

@bp.route("/api/groups", methods=["POST"])
def api_create_group():
    try:
        db = get_db()
        body = request.get_json(silent=True) or {}
        name = str(body.get("name", "Group") or "Group").strip()[:80] or "Group"
        for _ in range(5):
            code = _new_invite_code()
            try:
                cur = db.execute(
                    "INSERT INTO emergency_groups (invite_code, name) VALUES (?, ?)",
                    (code, name),
                )
                db.commit()
                row = db.execute(
                    "SELECT id, invite_code, name, created_at FROM emergency_groups WHERE id=?",
                    (cur.lastrowid,),
                ).fetchone()
                return jsonify(dict(row)), 201
            except sqlite3.IntegrityError:
                continue
        return jsonify({"error": "Could not create group", "retry": True}), 503
    except Exception:
        return jsonify({"error": "Could not create group", "retry": True}), 503

@bp.route("/api/locations", methods=["POST"])
def api_post_location():
    try:
        db = get_db()
        body = request.get_json(silent=True) or {}
        invite = str(body.get("invite_code", "")).strip()
        display = str(body.get("display_name", "")).strip()[:40]
        if not invite or not display:
            return jsonify({"error": "invite_code and display_name are required"}), 400
        try:
            lat = float(body.get("lat"))
            lng = float(body.get("lon", body.get("lng")))
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                return jsonify({"error": "Invalid coordinates"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid coordinates"}), 400
        accuracy = body.get("accuracy")
        if accuracy is not None:
            try:
                accuracy = float(accuracy)
                if accuracy < 0:
                    return jsonify({"error": "Invalid accuracy"}), 400
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid accuracy"}), 400
        group = db.execute(
            "SELECT id FROM emergency_groups WHERE invite_code=? COLLATE NOCASE",
            (invite,),
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404
        try:
            cur = db.execute(
                """INSERT INTO live_locations
                   (group_id, display_name, lat, lng, accuracy, expires_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now', '+2 hours'))""",
                (group["id"], display, lat, lng, accuracy),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "Invalid coordinates"}), 400
        row = db.execute(
            "SELECT id, expires_at FROM live_locations WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return jsonify(dict(row)), 201
    except Exception:
        return jsonify({"error": "Could not share location", "retry": True}), 503

@bp.route("/api/groups/<code>/locations")
def api_group_locations(code):
    try:
        db = get_db()
        group = db.execute(
            "SELECT id FROM emergency_groups WHERE invite_code=? COLLATE NOCASE",
            ((code or "").strip(),),
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404
        db.execute(
            "DELETE FROM live_locations WHERE expires_at <= datetime('now')"
        )
        db.commit()
        since = (request.args.get("since", "") or "").strip()
        sql = """SELECT display_name, lat, lng, accuracy, shared_at
                 FROM live_locations
                 WHERE group_id=? AND expires_at > datetime('now')"""
        params = [group["id"]]
        if since:
            norm = since.replace("T", " ").split("+")[0].split("Z")[0].strip()[:19]
            sql += " AND shared_at > ?"
            params.append(norm)
        sql += " ORDER BY shared_at DESC LIMIT 100"
        rows = db.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["lon"] = d["lng"]
            out.append(d)
        return jsonify(out)
    except Exception:
        return jsonify({"error": "Could not load locations", "retry": True}), 503

@bp.route("/api/earthquakes")
def api_earthquakes():
    try:
        from services.hazards_service import fetch_earthquakes
        db = get_db()
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        radius = request.args.get("radius_km", "500")
        try:
            lat_f = float(lat) if lat not in (None, "") else None
            lon_f = float(lon) if lon not in (None, "") else None
            radius_f = float(radius)
            if lat_f is not None and not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                return jsonify({"error": "Invalid coordinates"}), 400
            if not (10 <= radius_f <= 2000):
                return jsonify({"error": "radius_km must be 10-2000"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid coordinates"}), 400
        data, err = fetch_earthquakes(db, lat_f, lon_f, radius_f)
        if data:
            return jsonify(data)
        return jsonify({"error": err or "Earthquake data unavailable", "retry": True}), 503
    except Exception:
        return jsonify({"error": "Earthquake data unavailable", "retry": True}), 503

@bp.route("/api/fires")
def api_fires():
    try:
        from services.hazards_service import fetch_fires
        db = get_db()
        lat = request.args.get("lat", "14.6308")
        lon = request.args.get("lon", "121.0968")
        days = request.args.get("days", "1")
        try:
            lat_f = float(lat); lon_f = float(lon)
            if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                return jsonify({"error": "Invalid coordinates"}), 400
            days_i = int(days)
            if days_i not in (1, 2):
                return jsonify({"error": "days must be 1 or 2"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid coordinates"}), 400
        data, err = fetch_fires(db, lat_f, lon_f, days_i)
        if data:
            return jsonify(data)
        status = 503
        return jsonify({"error": err or "Fire data unavailable", "retry": True}), status
    except Exception:
        return jsonify({"error": "Fire data unavailable", "retry": True}), 503
