from flask import Blueprint, request, jsonify, current_app
from utils.db import get_db

bp = Blueprint("api", __name__)

import math
import secrets
import sqlite3
import string

_INVITE_ALPHABET = string.ascii_uppercase + string.digits


def _new_invite_code(n=6):
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(n))

@bp.route("/api/status")
def api_status():
    """Client-safe server status: build id + provider availability.

    Never exposes secret values — only booleans. The Settings page uses
    build_id to invalidate stale offline caches after a server restart.
    """
    def _has(key, prefix=None):
        v = (current_app.config.get(key, "") or "").strip()
        if not v or v.startswith("YOUR_"):
            return False
        return v.startswith(prefix) if prefix else True
    return jsonify({
        "build_id": current_app.config.get("STARTED_AT", ""),
        "is_demo": bool(current_app.config.get("IS_DEMO", True)),
        "providers": {
            "openweather": _has("OPENWEATHER_API_KEY"),
            "open_meteo": True,  # keyless fallback, always available online
            "mapbox": _has("MAPBOX_TOKEN", "pk."),
            "firms": _has("FIRMS_MAP_KEY"),
        },
    })

def _occupancy_status(row):
    """Return (pct, available_slots, status), tolerating unknown capacity.

    Sprint 2 imports carry capacity NULL until an admin sets real numbers;
    those rows report Status Unavailable with null figures instead of
    crashing (None arithmetic) or masquerading as Available.
    """
    cap, occ = row["capacity"], row["current_occupancy"]
    if cap is None or occ is None:
        return None, None, "Status Unavailable"
    pct = round(occ / cap * 100, 1) if cap else 0
    avail = cap - occ
    status = ("Full" if pct >= 100 else "Nearly Full" if pct >= 80
              else "Available" if row["operational_status"] == "Open"
              else "Status Unavailable")
    return pct, avail, status

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
        pct, avail, occ_status = _occupancy_status(c)
        d["occupancy_pct"]=pct; d["available_slots"]=avail; d["occupancy_status"]=occ_status
        if supply and supply not in (c["food_status"], c["water_status"], c["medicine_status"], c["hygiene_status"], c["basic_needs_status"]):
            continue
        if status and occ_status!=status:
            continue
        out.append(d)
    if sort=="name":
        out.sort(key=lambda x: x["name"].lower())
    elif sort=="available":
        # Unknown capacity sinks to the bottom, never masquerades as 0.
        out.sort(key=lambda x: x["available_slots"] if x["available_slots"] is not None else -1, reverse=True)
    elif sort=="occupancy":
        out.sort(key=lambda x: x["occupancy_pct"] if x["occupancy_pct"] is not None else -1, reverse=True)
    else:
        out.sort(key=lambda x: x["updated_at"], reverse=True)
    return jsonify(out)

@bp.route("/api/centers/version")
def api_centers_version():
    db = get_db()
    row = db.execute(
        "SELECT MAX(updated_at) AS max_updated_at, COUNT(*) AS count "
        "FROM evacuation_centers WHERE archived=0"
    ).fetchone()
    d = dict(row) if row else {}
    return jsonify({
        "max_updated_at": d.get("max_updated_at"),
        "count": d.get("count", 0),
    })

@bp.route("/api/centers/<int:cid>")
def api_center_detail(cid):
    db=get_db()
    c=db.execute("SELECT * FROM evacuation_centers WHERE id=? AND archived=0", (cid,)).fetchone()
    if not c: return jsonify({"error":"Not found"}),404
    d=dict(c)
    pct, avail, occ_status = _occupancy_status(c)
    d["occupancy_pct"]=pct; d["available_slots"]=avail
    d["occupancy_status"]=occ_status
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

@bp.route("/api/ncr-lgus")
def api_ncr_lgus():
    # Static reference: all 17 NCR LGUs with city-level coords for weather
    # lookup and search scoping. Open-Meteo grids are ~11km, so city-center
    # precision is sufficient; keep in sync with utils/seed.py coverage.
    return jsonify([
        {"name": "Caloocan", "lat": 14.6507, "lon": 120.9678},
        {"name": "Las Piñas", "lat": 14.4445, "lon": 120.9939},
        {"name": "Makati", "lat": 14.5547, "lon": 121.0244},
        {"name": "Malabon", "lat": 14.6625, "lon": 120.9780},
        {"name": "Mandaluyong", "lat": 14.5794, "lon": 121.0359},
        {"name": "Manila", "lat": 14.5995, "lon": 120.9842},
        {"name": "Marikina", "lat": 14.6507, "lon": 121.1029},
        {"name": "Muntinlupa", "lat": 14.4081, "lon": 121.0415},
        {"name": "Navotas", "lat": 14.6667, "lon": 120.9417},
        {"name": "Parañaque", "lat": 14.4793, "lon": 121.0198},
        {"name": "Pasay", "lat": 14.5378, "lon": 121.0014},
        {"name": "Pasig", "lat": 14.5764, "lon": 121.0851},
        {"name": "Pateros", "lat": 14.5445, "lon": 121.0687},
        {"name": "Quezon City", "lat": 14.6760, "lon": 121.0437},
        {"name": "San Juan", "lat": 14.6019, "lon": 121.0355},
        {"name": "Taguig", "lat": 14.5176, "lon": 121.0509},
        {"name": "Valenzuela", "lat": 14.7008, "lon": 120.9830},
    ])

_DEFAULT_LAT, _DEFAULT_LON = 14.6308, 121.0968

def _resolve_place(lat, lon, city):
    """Resolve query params to (lat_f, lon_f, label).

    Explicit coordinates win. A bare city name is geocoded (keyless
    Open-Meteo lookup) so typed places get their own grid. Returns
    (None, None, None, (body, status)) on 400/404 — callers return it
    directly. No silent default-grid substitution: serving Marikina data
    labeled "Masbate" is worse than a clear 404.
    """
    has_lat = lat not in (None, "")
    has_lon = lon not in (None, "")
    label = (city or "").strip() or None
    if has_lat or has_lon:
        try:
            lat_f, lon_f = float(lat), float(lon)
            if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                return None, None, None, (jsonify({"error": "Invalid coordinates"}), 400)
            return lat_f, lon_f, label, None
        except (TypeError, ValueError):
            return None, None, None, (jsonify({"error": "Invalid coordinates"}), 400)
    if label:
        from services.weather_service import geocode_city
        hit = geocode_city(label)
        if not hit:
            return None, None, None, (jsonify(
                {"error": f"Place not found: {label}. Check spelling or pick an NCR LGU."}), 404)
        glat, glon, _gname = hit
        return glat, glon, label, None
    return _DEFAULT_LAT, _DEFAULT_LON, None, None

@bp.route("/api/weather")
def api_weather():
    try:
        from services.weather_service import fetch_weather
        db=get_db()
        lat=request.args.get("lat")
        lon=request.args.get("lon")
        city=request.args.get("city")
        lat_f, lon_f, label, err = _resolve_place(lat, lon, city)
        if err:
            return err
        data, err = fetch_weather(db, lat_f, lon_f, label)
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
        lat=request.args.get("lat")
        lon=request.args.get("lon")
        city=request.args.get("city")
        lat_f, lon_f, label, err = _resolve_place(lat, lon, city)
        if err:
            return err
        data, err = fetch_air_quality(db, lat_f, lon_f, label)
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
        lat=request.args.get("lat")
        lon=request.args.get("lon")
        city=request.args.get("city")
        lat_f, lon_f, label, err = _resolve_place(lat, lon, city)
        if err:
            return err
        w_data, w_err = fetch_weather(db, lat_f, lon_f, label)
        aq_data, aq_err = fetch_air_quality(db, lat_f, lon_f, label)
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

@bp.route("/api/groups/<code>")
def api_group_info(code):
    try:
        db = get_db()
        group = db.execute(
            "SELECT id, invite_code, name, created_at FROM emergency_groups WHERE invite_code=? COLLATE NOCASE",
            ((code or "").strip(),),
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404
        live = db.execute(
            "SELECT COUNT(*) AS n FROM live_locations WHERE group_id=? AND expires_at > datetime('now')",
            (group["id"],),
        ).fetchone()
        out = dict(group)
        out["live_count"] = live["n"] if live else 0
        return jsonify(out)
    except Exception:
        return jsonify({"error": "Could not load group", "retry": True}), 503

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
            # Upsert per person: re-sharing replaces the sender's previous pin
            # so the live list stays one row per display_name (case-insensitive).
            db.execute(
                "DELETE FROM live_locations WHERE group_id=? AND display_name=? COLLATE NOCASE",
                (group["id"], display),
            )
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


def _haversine_km(lat1, lon1, lat2, lon2):
    try:
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))
    except Exception:
        return float("inf")


@bp.route("/api/announcements")
def api_announcements():
    """Public feed of announcements.

    Query params (all optional):
      city — exact city match for scope='city' rows
      lat / lon — user coords for scope='radius' rows (haversine <= radius_km)
      history=1 — include expired/upcoming rows too (bell history), newest
        first, each flagged with `expired`; otherwise only live rows.

    Always returns scope='all' rows. City/radius rows only match when the
    corresponding param is supplied, so targeted messages don't leak to
    everyone. Live mode: only rows with is_active=1 and now in
    [starts_at, ends_at].
    """
    try:
        db = get_db()
        city = (request.args.get("city", "") or "").strip()
        lat = request.args.get("lat")
        lon = request.args.get("lon", request.args.get("lng"))
        history = (request.args.get("history", "") or "").strip() == "1"
        try:
            lat_f = float(lat) if lat not in (None, "") else None
            lon_f = float(lon) if lon not in (None, "") else None
            if (lat_f is not None and lon_f is None) or (lat_f is None and lon_f is not None):
                return jsonify({"error": "Both lat and lon are required"}), 400
            if lat_f is not None and lon_f is not None:
                if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                    return jsonify({"error": "Invalid coordinates"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid coordinates"}), 400
        if history:
            rows = db.execute(
                """SELECT id, title, message, scope, city, center_lat, center_lng,
                          radius_km, severity, starts_at, ends_at, created_at,
                          CASE WHEN datetime('now') < datetime(starts_at)
                                 OR datetime('now') > datetime(ends_at)
                               THEN 1 ELSE 0 END AS expired
                   FROM announcements
                   WHERE is_active=1
                   ORDER BY starts_at DESC"""
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT id, title, message, scope, city, center_lat, center_lng,
                          radius_km, severity, starts_at, ends_at, created_at
               FROM announcements
               WHERE is_active=1
                 AND datetime('now') >= datetime(starts_at)
                 AND datetime('now') <= datetime(ends_at)
               ORDER BY starts_at DESC, id DESC"""
            ).fetchall()
        out = []
        from utils.announcements import dedup_message
        for r in rows:
            d = dict(r)
            d["message"] = dedup_message(d.get("title"), d.get("message"))
            scope = d.get("scope", "all")
            if scope == "city":
                if not city or (d.get("city") or "").strip().lower() != city.lower():
                    continue
            elif scope == "radius":
                if lat_f is None or lon_f is None:
                    continue
                try:
                    dist = _haversine_km(lat_f, lon_f, float(d["center_lat"]), float(d["center_lng"]))
                except (TypeError, ValueError):
                    continue
                if dist > float(d["radius_km"] or 0):
                    continue
                d["distance_km"] = round(dist, 1)
            # scope 'all' always included
            out.append(d)
        return jsonify(out)
    except Exception:
        return jsonify({"error": "Could not load announcements", "retry": True}), 503

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
            if (lat_f is None) != (lon_f is None):
                return jsonify({"error": "Both lat and lon are required"}), 400
            if lat_f is not None and lon_f is not None:
                if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
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
