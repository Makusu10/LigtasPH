from flask import Blueprint, request, jsonify, current_app, Response
from utils.db import get_db, get_meta
from utils.api_errors import api_error
from utils.validation import validate_coordinates, parse_pagination
from utils.idempotency import get_idempotency_key, claim_idempotency, record_idempotency
from utils.ratelimit import limiter

bp = Blueprint("api", __name__)

import json
import hashlib
import datetime as _dt
import math
import re
import secrets
import sqlite3
import string
from pathlib import Path

_BASEDIR = Path(__file__).resolve().parent.parent
_EVAC_GEOJSON = _BASEDIR / "data" / "ncr_evacuation_centers.geojson"
_OPENAPI_SPEC = _BASEDIR / "static" / "openapi.yaml"

_SITE_RE = re.compile(r"([A-Z][A-Z /&.\-]+?)\s*[•·|]\s*(TEMPORARY|PERMANENT)\b")

# Public list contract (GH #4, API-001): import-provenance internals never
# leave the server in list responses — they identify unverified rows for
# rumor targeting. Full detail stays on GET /api/centers/<id>.
_LIST_DROP = frozenset({
    "notes", "source", "verified", "needs_review", "review_reason",
    "created_at",
})
# Same rule for the offline GeoJSON export (API-002): display fields only.
# Dropped: *_input raw strings, confidence, geocode_provider/query,
# uncertainty_radius_m, verified, needs_review, review_reason.
_GEOJSON_KEEP = frozenset({
    "name", "barangay_resolved", "municipality_input",
    "facility_type", "facility_status",
})
# Stripped export bytes, rebuilt only when the source file changes
# (immutable per deploy in practice). Avoids a 608 KB parse per request.
_GEOJSON_CACHE = {"mtime": None, "etag": None, "body": None}

def site_info(row):
    """Return (site_kind, facility_type) parsed from import notes.

    Sprint 2 import notes embed "<TYPE> • TEMPORARY|PERMANENT • ...".
    That flag describes the SITE's nature — a standing evacuation center
    vs. a school/court activated during disasters — NOT live open/closed,
    so it is surfaced with honest wording, never as occupancy.
    Returns (None, None) for hand-entered rows without import notes.
    """
    try:
        notes = row["notes"] or ""
    except (KeyError, IndexError, TypeError):
        return None, None
    m = _SITE_RE.search(notes or "")
    if not m:
        return None, None
    ftype, perm = m.group(1).strip(), m.group(2)
    kind = ("Permanent evacuation center" if perm == "PERMANENT"
            else "Temporary site — activated during disasters")
    return kind, ftype.title() if ftype else None

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
    def _meta(key):
        try:
            from utils.db import get_meta as _get_meta
            return _get_meta(get_db(), key)
        except Exception:
            return ""
    return jsonify({
        "build_id": current_app.config.get("STARTED_AT", ""),
        "is_demo": bool(current_app.config.get("IS_DEMO", True)),
        "dataset": {  # GH #7: content identifiers only, never secret values
            "sha256": _meta("geojson.sha256"),
            "pending_sha256": _meta("geojson.pending_sha256"),
            "imported_at": _meta("geojson.imported_at"),
        },
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
@limiter.limit("120 per minute")
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
        # Escape LIKE wildcards so a "q=%" probe matches literally instead
        # of amplifying into a full-table scan (GH #7 serving-cost note).
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += " AND (name LIKE ? ESCAPE '\\' OR city LIKE ? ESCAPE '\\' OR address LIKE ? ESCAPE '\\')"
        params.extend([like,like,like])
    if city:
        sql += " AND city=?"
        params.append(city)
    centers = db.execute(sql, params).fetchall()
    out=[]
    for c in centers:
        d={k: v for k, v in dict(c).items() if k not in _LIST_DROP}
        pct, avail, occ_status = _occupancy_status(c)
        d["occupancy_pct"]=pct; d["available_slots"]=avail; d["occupancy_status"]=occ_status
        kind, ftype = site_info(c)
        d["site_kind"]=kind; d["facility_type"]=ftype
        try: d["location_verified"]=bool(c["verified"])
        except (KeyError, IndexError, TypeError): d["location_verified"]=False
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

    # GH #7: the default list response is bounded (50 rows + pagination
    # headers). Clients that need the whole dataset for clustering/cards
    # pass an explicit ?limit= (up to 1000) — see map/directory/home/settings.
    limit, offset, page, is_paginated = parse_pagination(
        request.args, default_limit=50, max_limit=1000)
    total_count = len(out)
    paged_out = out[offset : offset + limit] if is_paginated and limit is not None else out

    envelope = (request.args.get("envelope", "").strip().lower() in ("1", "true")) or (
        request.headers.get("Accept") == "application/vnd.ligtasph.v2+json"
    )
    if envelope:
        total_pages = math.ceil(total_count / limit) if (is_paginated and limit) else 1
        resp = jsonify({
            "data": paged_out,
            "pagination": {
                "page": page,
                "pageSize": limit or total_count,
                "total": total_count,
                "totalPages": total_pages,
            },
        })
    else:
        resp = jsonify(paged_out)

    resp.headers["X-Total-Count"] = str(total_count)
    if is_paginated and limit is not None:
        resp.headers["X-Page"] = str(page)
        resp.headers["X-Per-Page"] = str(limit)
        resp.headers["X-Total-Pages"] = str(math.ceil(total_count / limit) if limit else 1)
    # GH #7: dataset provenance rides on every list response so clients and
    # the SW staleness banner (#5) can label data age. Empty when no import
    # has been recorded yet (fresh DBs serve seed rows only).
    resp.headers["X-Dataset-Sha256"] = get_meta(db, "geojson.sha256")
    resp.headers["X-Dataset-Imported-At"] = get_meta(db, "geojson.imported_at")
    return resp

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
    if not c:
        return api_error("Not found", status_code=404, code="NOT_FOUND")
    d=dict(c)
    pct, avail, occ_status = _occupancy_status(c)
    d["occupancy_pct"]=pct; d["available_slots"]=avail
    d["occupancy_status"]=occ_status
    kind, ftype = site_info(c)
    d["site_kind"]=kind; d["facility_type"]=ftype
    try: d["location_verified"]=bool(c["verified"])
    except (KeyError, IndexError, TypeError): d["location_verified"]=False
    return jsonify(d)

@bp.route("/api/evac-centers.geojson")
@limiter.limit("30 per minute")
def api_evac_centers_geojson():
    """Serve the stripped Sprint-2 evacuation-center dataset for the offline
    Service Worker precache (the Mapbox GL map builds from /api/centers).

    Display fields only — no import provenance (GH #4, API-002). Bytes are
    rebuilt only when the source file changes; ETag + 304 supported.
    Cache-Control is no-store (API data, consistent app-wide) — the SW
    Cache API precaches it explicitly, and #5 will label its age via the
    X-Dataset-* headers below.
    """
    if not _EVAC_GEOJSON.exists():
        return api_error("evac dataset missing", status_code=404, code="NOT_FOUND")
    try:
        mtime = _EVAC_GEOJSON.stat().st_mtime
    except OSError:
        return api_error("evac dataset missing", status_code=404, code="NOT_FOUND")
    if _GEOJSON_CACHE["mtime"] != mtime or not _GEOJSON_CACHE["body"]:
        try:
            raw_bytes = _EVAC_GEOJSON.read_bytes()
            raw = json.loads(raw_bytes.decode("utf-8"))
        except (OSError, ValueError):
            return api_error("evac dataset unreadable", status_code=503,
                             code="SERVICE_UNAVAILABLE", retry=True)
        feats = []
        for f in raw.get("features", []) or []:
            props = (f.get("properties") or {}) if isinstance(f, dict) else {}
            feats.append({
                "type": "Feature",
                "geometry": f.get("geometry") if isinstance(f, dict) else None,
                "properties": {k: props.get(k) for k in _GEOJSON_KEEP},
            })
        body = json.dumps({"type": "FeatureCollection", "features": feats})
        _GEOJSON_CACHE.update(
            mtime=mtime,
            etag='"%s"' % hashlib.sha1(body.encode("utf-8")).hexdigest(),
            body=body,
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
        )
    etag = _GEOJSON_CACHE["etag"]
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304)
    try:
        file_mtime = _dt.datetime.fromtimestamp(
            mtime, tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OSError, OverflowError, ValueError):
        file_mtime = ""
    return Response(
        _GEOJSON_CACHE["body"],
        mimetype="application/geo+json",
        headers={
            "Cache-Control": "no-store",
            "ETag": etag,
            "X-Dataset-Build": current_app.config.get("STARTED_AT", ""),
            "X-Dataset-File-Mtime": file_mtime,
            "X-Dataset-Sha256": _GEOJSON_CACHE.get("sha256") or "",
        },
    )

@bp.route("/api/centers/<int:cid>/status")
def api_center_status(cid):
    """Structured live-supply status for a center. The current dataset has no
    food/water/capacity telemetry, so this returns an explicit 'not available'
    state — map popups must NOT fabricate numbers. Forward-compatible
    integration point for future live reporting.
    """
    db = get_db()
    c = db.execute("SELECT id FROM evacuation_centers WHERE id=? AND archived=0", (cid,)).fetchone()
    if not c:
        return api_error("Not found", status_code=404, code="NOT_FOUND")
    return jsonify({
        "center_id": cid,
        "available": False,
        "status": "not_available",
        "message": "Live supply data not yet available — see crowd reports on the map.",
        "source": "none",
        "updated_at": None,
    })

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

    limit, offset, page, is_paginated = parse_pagination(request.args)
    out = [dict(r) for r in rows]
    total_count = len(out)
    paged_out = out[offset : offset + limit] if is_paginated and limit is not None else out

    envelope = (request.args.get("envelope", "").strip().lower() in ("1", "true")) or (
        request.headers.get("Accept") == "application/vnd.ligtasph.v2+json"
    )
    if envelope:
        total_pages = math.ceil(total_count / limit) if (is_paginated and limit) else 1
        resp = jsonify({
            "data": paged_out,
            "pagination": {
                "page": page,
                "pageSize": limit or total_count,
                "total": total_count,
                "totalPages": total_pages,
            },
        })
    else:
        resp = jsonify(paged_out)

    resp.headers["X-Total-Count"] = str(total_count)
    if is_paginated and limit is not None:
        resp.headers["X-Page"] = str(page)
        resp.headers["X-Per-Page"] = str(limit)
        resp.headers["X-Total-Pages"] = str(math.ceil(total_count / limit) if limit else 1)
    return resp

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
        lat_f, lon_f, err = validate_coordinates(lat, lon, required=True)
        if err:
            return None, None, None, api_error(err, status_code=400, code="INVALID_COORDINATES")
        return lat_f, lon_f, label, None
    if label:
        from services.weather_service import geocode_city
        hit = geocode_city(label)
        if not hit:
            return None, None, None, api_error(
                f"Place not found: {label}. Check spelling or pick an NCR LGU.",
                status_code=404,
                code="PLACE_NOT_FOUND",
            )
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
        return api_error(err or "Weather unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)
    except Exception:
        return api_error("Weather unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)

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
        return api_error(err or "Air quality unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)
    except Exception:
        return api_error("Air quality unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)

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
        return api_error("Environment data unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)

@bp.route("/api/groups", methods=["POST"])
@limiter.limit("10 per minute", methods=["POST"])
def api_create_group():
    try:
        db = get_db()
        raw_payload = request.get_data() or b"{}"
        idem_key = get_idempotency_key(request)
        if idem_key:
            state, cached, err_resp = claim_idempotency(db, idem_key, raw_payload)
            if err_resp:
                return err_resp
            if state == "succeeded" and cached:
                return Response(cached["response_body"], status=cached["status_code"], mimetype="application/json")

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
                out = dict(row)
                if idem_key:
                    record_idempotency(db, idem_key, 201, json.dumps(out), succeeded=True)
                return jsonify(out), 201
            except sqlite3.IntegrityError:
                continue
        if idem_key:
            record_idempotency(db, idem_key, 503, json.dumps({"error": "Could not create group", "retry": True}), succeeded=False)
        return api_error("Could not create group", status_code=503, code="GROUP_CREATION_FAILED", retry=True)
    except Exception:
        return api_error("Could not create group", status_code=503, code="INTERNAL_ERROR", retry=True)

@bp.route("/api/groups/<code>")
def api_group_info(code):
    try:
        db = get_db()
        group = db.execute(
            "SELECT id, invite_code, name, created_at FROM emergency_groups WHERE invite_code=? COLLATE NOCASE",
            ((code or "").strip(),),
        ).fetchone()
        if not group:
            return api_error("Group not found", status_code=404, code="NOT_FOUND")
        live = db.execute(
            "SELECT COUNT(*) AS n FROM live_locations WHERE group_id=? AND expires_at > datetime('now')",
            (group["id"],),
        ).fetchone()
        out = dict(group)
        out["live_count"] = live["n"] if live else 0
        return jsonify(out)
    except Exception:
        return api_error("Could not load group", status_code=503, code="INTERNAL_ERROR", retry=True)

@bp.route("/api/locations", methods=["POST"])
@limiter.limit("60 per minute", methods=["POST"])
def api_post_location():
    try:
        db = get_db()
        raw_payload = request.get_data() or b"{}"
        idem_key = get_idempotency_key(request)
        if idem_key:
            state, cached, err_resp = claim_idempotency(db, idem_key, raw_payload)
            if err_resp:
                return err_resp
            if state == "succeeded" and cached:
                return Response(cached["response_body"], status=cached["status_code"], mimetype="application/json")

        body = request.get_json(silent=True) or {}
        invite = str(body.get("invite_code", "")).strip()
        display = str(body.get("display_name", "")).strip()[:40]
        if not invite or not display:
            return api_error("invite_code and display_name are required", status_code=400, code="MISSING_REQUIRED_FIELDS")

        lat_raw = body.get("lat")
        lon_raw = body.get("lon") if "lon" in body else body.get("lng")
        lat_f, lon_f, coord_err = validate_coordinates(lat_raw, lon_raw, required=True)
        if coord_err:
            return api_error(coord_err, status_code=400, code="INVALID_COORDINATES")

        accuracy = body.get("accuracy")
        if accuracy is not None:
            try:
                accuracy = float(accuracy)
                if accuracy < 0:
                    return api_error("Invalid accuracy", status_code=400, code="INVALID_ACCURACY")
            except (TypeError, ValueError):
                return api_error("Invalid accuracy", status_code=400, code="INVALID_ACCURACY")

        group = db.execute(
            "SELECT id FROM emergency_groups WHERE invite_code=? COLLATE NOCASE",
            (invite,),
        ).fetchone()
        if not group:
            return api_error("Group not found", status_code=404, code="NOT_FOUND")

        # Atomic UPSERT per member: re-sharing replaces previous coordinates
        # and preserves casing updates atomically via ON CONFLICT
        try:
            db.execute(
                """INSERT INTO live_locations
                   (group_id, display_name, lat, lng, accuracy, expires_at, shared_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now', '+2 hours'), datetime('now'))
                   ON CONFLICT(group_id, display_name COLLATE NOCASE) DO UPDATE SET
                       display_name=excluded.display_name,
                       lat=excluded.lat,
                       lng=excluded.lng,
                       accuracy=excluded.accuracy,
                       expires_at=excluded.expires_at,
                       shared_at=datetime('now')""",
                (group["id"], display, lat_f, lon_f, accuracy),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return api_error("Invalid coordinates", status_code=400, code="INVALID_COORDINATES")

        row = db.execute(
            "SELECT id, expires_at FROM live_locations WHERE group_id=? AND display_name=? COLLATE NOCASE",
            (group["id"], display),
        ).fetchone()
        out = dict(row)
        if idem_key:
            record_idempotency(db, idem_key, 201, json.dumps(out), succeeded=True)
        return jsonify(out), 201
    except Exception:
        return api_error("Could not share location", status_code=503, code="INTERNAL_ERROR", retry=True)

@bp.route("/api/groups/<code>/locations")
def api_group_locations(code):
    try:
        db = get_db()
        group = db.execute(
            "SELECT id FROM emergency_groups WHERE invite_code=? COLLATE NOCASE",
            ((code or "").strip(),),
        ).fetchone()
        if not group:
            return api_error("Group not found", status_code=404, code="NOT_FOUND")
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
        return api_error("Could not load locations", status_code=503, code="INTERNAL_ERROR", retry=True)


RAIN_INTENSITIES = ("none", "light", "heavy")
RAIN_WINDOW_HOURS = 3

@bp.route("/api/rain-reports", methods=["POST"])
@limiter.limit("10 per minute", methods=["POST"])
def api_rain_report():
    """Community ground truth: is it raining where you are? Anonymous —
    intensity plus optional city/coords only, no identity, no account link.
    Reports count for RAIN_WINDOW_HOURS, then expire out of reads."""
    try:
        db = get_db()
        body = request.get_json(silent=True) or {}
        intensity = str(body.get("intensity", "")).strip().lower()
        if intensity not in RAIN_INTENSITIES:
            return api_error("intensity must be one of: none, light, heavy",
                             status_code=400, code="MISSING_REQUIRED_FIELDS")
        city = str(body.get("city", "") or "").strip()[:80] or None
        lat = lng = None
        if body.get("lat") is not None or body.get("lon") is not None or body.get("lng") is not None:
            lat, lng, coord_err = validate_coordinates(
                body.get("lat"), body.get("lon", body.get("lng")), required=True)
            if coord_err:
                return api_error("Invalid coordinates", status_code=400,
                                 code="INVALID_COORDINATES")
        flooding = None
        if intensity == "heavy":
            f = body.get("flooding", None)
            if f is not None:
                flooding = 1 if str(f).strip().lower() in ("1", "true", "yes") else 0
        cur = db.execute(
            "INSERT INTO rain_reports (city, lat, lng, intensity, flooding)"
            " VALUES (?,?,?,?,?)",
            (city, lat, lng, intensity, flooding),
        )
        # Prune day-old rows opportunistically; live reads only see the window.
        db.execute("DELETE FROM rain_reports WHERE reported_at <= datetime('now', '-24 hours')")
        db.commit()
        return jsonify({"id": cur.lastrowid, "intensity": intensity}), 201
    except Exception:
        return api_error("Could not save report", status_code=503,
                         code="INTERNAL_ERROR", retry=True)


@bp.route("/api/rain-reports")
@limiter.limit("60 per minute")
def api_rain_summary():
    """Aggregate counts over live (unexpired) reports, optionally narrowed
    to a city. Counts only — individual rows are never returned, so no
    single reporter's pin is exposed."""
    try:
        db = get_db()
        city = (request.args.get("city", "") or "").strip()
        sql = ("SELECT intensity, flooding, COUNT(*) AS n, MAX(reported_at) AS latest"
               " FROM rain_reports WHERE reported_at > datetime('now', '-3 hours')")
        params = []
        if city:
            sql += " AND city=? COLLATE NOCASE"
            params.append(city)
        sql += " GROUP BY intensity, flooding"
        rows = db.execute(sql, params).fetchall()
        out = {"city": city or None, "window_hours": RAIN_WINDOW_HOURS,
               "total": 0, "none": 0, "light": 0, "heavy": 0,
               "flooding": 0, "latest_at": None}
        for r in rows:
            out["total"] += r["n"]
            if r["intensity"] in out:
                out[r["intensity"]] += r["n"]
            if r["flooding"] == 1:
                out["flooding"] += r["n"]
            if r["latest"] and (out["latest_at"] is None or r["latest"] > out["latest_at"]):
                out["latest_at"] = r["latest"]
        return jsonify(out)
    except Exception:
        return api_error("Could not load rain reports", status_code=503,
                         code="INTERNAL_ERROR", retry=True)


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
        lon = request.args.get("lon") if "lon" in request.args else request.args.get("lng")
        history = (request.args.get("history", "") or "").strip() == "1"

        lat_f, lon_f, coord_err = validate_coordinates(lat, lon, required=False)
        if coord_err:
            return api_error(coord_err, status_code=400, code="INVALID_COORDINATES")

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

        limit, offset, page, is_paginated = parse_pagination(request.args)
        total_count = len(out)
        paged_out = out[offset : offset + limit] if is_paginated and limit is not None else out

        envelope = (request.args.get("envelope", "").strip().lower() in ("1", "true")) or (
            request.headers.get("Accept") == "application/vnd.ligtasph.v2+json"
        )
        if envelope:
            total_pages = math.ceil(total_count / limit) if (is_paginated and limit) else 1
            resp = jsonify({
                "data": paged_out,
                "pagination": {
                    "page": page,
                    "pageSize": limit or total_count,
                    "total": total_count,
                    "totalPages": total_pages,
                },
            })
        else:
            resp = jsonify(paged_out)

        resp.headers["X-Total-Count"] = str(total_count)
        if is_paginated and limit is not None:
            resp.headers["X-Page"] = str(page)
            resp.headers["X-Per-Page"] = str(limit)
            resp.headers["X-Total-Pages"] = str(math.ceil(total_count / limit) if limit else 1)
        return resp
    except Exception:
        return api_error("Could not load announcements", status_code=503, code="INTERNAL_ERROR", retry=True)

@bp.route("/api/earthquakes")
def api_earthquakes():
    try:
        from services.hazards_service import fetch_earthquakes
        db = get_db()
        lat = request.args.get("lat")
        lon = request.args.get("lon")
        radius = request.args.get("radius_km", "500")

        lat_f, lon_f, coord_err = validate_coordinates(lat, lon, required=False)
        if coord_err:
            return api_error(coord_err, status_code=400, code="INVALID_COORDINATES")

        try:
            radius_f = float(radius)
            if not (10 <= radius_f <= 2000):
                return api_error("radius_km must be 10-2000", status_code=400, code="INVALID_RADIUS")
        except (TypeError, ValueError):
            return api_error("Invalid coordinates", status_code=400, code="INVALID_COORDINATES")

        data, err = fetch_earthquakes(db, lat_f, lon_f, radius_f)
        if data:
            return jsonify(data)
        return api_error(err or "Earthquake data unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)
    except Exception:
        return api_error("Earthquake data unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)

@bp.route("/api/fires")
def api_fires():
    try:
        from services.hazards_service import fetch_fires
        db = get_db()
        lat = request.args.get("lat", "14.6308")
        lon = request.args.get("lon", "121.0968")
        days = request.args.get("days", "1")

        lat_f, lon_f, coord_err = validate_coordinates(lat, lon, required=False)
        if coord_err:
            return api_error(coord_err, status_code=400, code="INVALID_COORDINATES")

        try:
            days_i = int(days)
            if days_i not in (1, 2):
                return api_error("days must be 1 or 2", status_code=400, code="INVALID_DAYS")
        except (TypeError, ValueError):
            return api_error("Invalid coordinates", status_code=400, code="INVALID_COORDINATES")

        data, err = fetch_fires(db, lat_f, lon_f, days_i)
        if data:
            return jsonify(data)
        return api_error(err or "Fire data unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)
    except Exception:
        return api_error("Fire data unavailable", status_code=503, code="SERVICE_UNAVAILABLE", retry=True)

@bp.route("/api/openapi.yaml")
def api_openapi_spec():
    """Stream the OpenAPI 3.1 contract specification."""
    if not _OPENAPI_SPEC.exists():
        return api_error("OpenAPI specification missing", status_code=404, code="NOT_FOUND")
    return Response(
        _OPENAPI_SPEC.read_text(encoding="utf-8"),
        mimetype="application/yaml",
        headers={"Cache-Control": "public, max-age=3600"},
    )

