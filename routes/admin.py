from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
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
    total_capacity = sum((c["capacity"] or 0) for c in centers)
    total_occ = sum((c["current_occupancy"] or 0) for c in centers)
    available = nearly = full = low_supply = unknown = 0
    for c in centers:
        if c["capacity"] is None or c["current_occupancy"] is None:
            unknown += 1
        else:
            pct = c["current_occupancy"]/c["capacity"]*100 if c["capacity"] else 0
            if pct >=100: full+=1
            elif pct>=80: nearly+=1
            else: available+=1
        if c["food_status"] in ("Low",) or c["water_status"] in ("Low",) or c["medicine_status"] in ("Low",):
            low_supply+=1
    recent = db.execute("SELECT * FROM evacuation_centers WHERE archived=0 ORDER BY updated_at DESC LIMIT 5").fetchall()
    stale = db.execute("SELECT * FROM evacuation_centers WHERE archived=0 AND julianday('now') - julianday(updated_at) > 7 ORDER BY updated_at ASC LIMIT 5").fetchall()
    return render_template("admin/dashboard.html", total=total, available=available, nearly=nearly, full=full, unknown=unknown, total_capacity=total_capacity, total_occ=total_occ, low_supply=low_supply, recent=recent, stale=stale)

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
    # Times are typed in Philippine time (UTC+8, where the admins sit) but the
    # API compares against datetime('now') = UTC. Convert Manila -> UTC on
    # input so "show from right now" is live on the next refresh, not 8h late.
    # datetime-local "YYYY-MM-DDTHH:MM" -> UTC "YYYY-MM-DD HH:MM:SS".
    _MANILA = _dt.timezone(_dt.timedelta(hours=8))
    def _norm(v):
        v = (v or "").strip().replace("T", " ")[:16]
        if len(v) == 16:
            v += ":00"
        return v
    starts_raw, ends_raw = _norm(starts_raw), _norm(ends_raw)
    try:
        s = _dt.datetime.strptime(starts_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_MANILA)
        e = _dt.datetime.strptime(ends_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_MANILA)
        if not s < e:
            errors.append("End time must be after start time.")
        starts_at = s.astimezone(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ends_at = e.astimezone(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        errors.append("Start and end times are required (valid date/time).")
        starts_at = ends_at = ""
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
    import datetime as _dt2
    from utils.announcements import dedup_message
    _MANILA2 = _dt2.timezone(_dt2.timedelta(hours=8))
    shown = []
    for r in rows:
        d = dict(r)
        d["message"] = dedup_message(d.get("title"), d.get("message"))
        for k in ("starts_at", "ends_at"):
            try:
                d[k + "_manila"] = (
                    _dt2.datetime.strptime(d[k], "%Y-%m-%d %H:%M:%S")
                    .replace(tzinfo=_dt2.timezone.utc).astimezone(_MANILA2)
                    .strftime("%Y-%m-%d %H:%M")
                )
            except (ValueError, TypeError):
                d[k + "_manila"] = d[k]
        shown.append(d)
    cities = db.execute(
        "SELECT DISTINCT city FROM evacuation_centers WHERE archived=0 ORDER BY city"
    ).fetchall()
    return render_template("admin/announcements.html", announcements=shown, cities=cities)


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
        occupancy = int(request.form.get("current_occupancy", c["current_occupancy"] or 0))
    except (TypeError, ValueError):
        flash("Occupancy must be a whole number.", "danger")
        return redirect(url_for("admin.centers")), 400
    # Sprint 2 imports have capacity NULL until an admin sets real numbers.
    cap_raw = (request.form.get("capacity") or "").strip()
    if c["capacity"] is None:
        if not cap_raw:
            flash("Set capacity first — occupancy cannot be tracked without it.", "danger")
            return redirect(url_for("admin.centers")), 400
        try:
            capacity = int(cap_raw)
        except (TypeError, ValueError):
            capacity = 0
        if capacity <= 0:
            flash("Capacity must be a positive whole number.", "danger")
            return redirect(url_for("admin.centers")), 400
    elif cap_raw:
        try:
            capacity = int(cap_raw)
        except (TypeError, ValueError):
            capacity = 0
        if capacity <= 0 or capacity < occupancy:
            flash(f"Capacity must be a whole number at least {occupancy}.", "danger")
            return redirect(url_for("admin.centers")), 400
    else:
        capacity = c["capacity"]
    if not (0 <= occupancy <= capacity):
        flash(f"Occupancy must be 0–{capacity}.", "danger")
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
        """UPDATE evacuation_centers SET capacity=?, current_occupancy=?, food_status=?, water_status=?,
           medicine_status=?, hygiene_status=?, basic_needs_status=?, operational_status=?,
           contact_number=?, notes=?, updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=?""",
        (capacity, occupancy, supplies["food_status"], supplies["water_status"], supplies["medicine_status"],
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


@bp.route("/admin/keys", methods=["GET", "POST"])
@login_required
def api_keys():
    from flask import current_app
    from utils import envkeys
    if request.method == "POST":
        changed = envkeys.save({k: request.form.get(k, "") for k in envkeys.MANAGED_KEYS})
        # Apply live immediately so providers work without a restart.
        for k in changed:
            current_app.config[k] = (request.form.get(k, "") or "").strip()
        if changed:
            flash("Saved: " + ", ".join(changed) + ". Applied live; restart only if clients look stale.", "success")
        else:
            flash("Nothing changed — empty fields keep their current values.", "info")
        return redirect(url_for("admin.api_keys"))
    live = {k: current_app.config.get(k, "") for k in envkeys.MANAGED_KEYS}
    return render_template("admin/keys.html", entries=envkeys.entries(live), env_path=str(envkeys.ENV_PATH))


@bp.route("/admin/restart", methods=["POST"])
@login_required
def restart_app():
    """Restart the app process so updates reflect server-side; clients pick
    up the new build_id via /api/status and refresh cached feeds.

    Refused under production servers (gunicorn/waitress) where re-exec would
    escape process management — redeploy there instead.
    """
    import os
    import sys
    import threading
    import time
    prog = (sys.argv[0] if sys.argv else "").lower()
    if (os.environ.get("SERVER_SOFTWARE", "").lower().startswith(("gunicorn", "waitress"))
            or "gunicorn" in prog or "waitress" in prog):
        flash("Restart is disabled under this server — redeploy to apply changes.", "warning")
        return redirect(url_for("admin.api_keys"))

    def _do():
        time.sleep(1.0)
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception:
            os._exit(3)  # noqa: SLF001 — last resort so a supervisor restarts us

    threading.Thread(target=_do, daemon=True).start()
    flash("Restarting. the app will be back in a few seconds. Clients refresh cached data automatically.", "info")
    return redirect(url_for("admin.api_keys"))


@bp.route("/admin/analytics")
@login_required
def analytics():
    """Server analytics: traffic, performance, uptime, content totals.

    "Online users" is approximated honestly as page-view counts — the app
    has no accounts or tracking, so no per-user identity exists to count.
    """
    import datetime as _dt
    from pathlib import Path
    db = get_db()

    def _count(sql, args=()):
        try:
            r = db.execute(sql, args).fetchone()
            return r[0] if r else 0
        except Exception:
            return 0

    visits_24h = _count("SELECT COUNT(*) FROM visits WHERE ts >= datetime('now', '-1 day')")
    visits_1h = _count("SELECT COUNT(*) FROM visits WHERE ts >= datetime('now', '-1 hour')")
    visits_5m = _count("SELECT COUNT(*) FROM visits WHERE ts >= datetime('now', '-5 minutes')")

    # Hourly buckets for the last 24h (oldest -> newest) for the bar chart.
    hours = []
    try:
        rows = db.execute(
            """SELECT strftime('%Y-%m-%d %H:00', ts) AS h, COUNT(*) AS n
               FROM visits WHERE ts >= datetime('now', '-1 day')
               GROUP BY h ORDER BY h""").fetchall()
        by_h = {r["h"]: r["n"] for r in rows}
        now = _dt.datetime.now(_dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
        for i in range(23, -1, -1):
            slot = now - _dt.timedelta(hours=i)
            key = slot.strftime("%Y-%m-%d %H:00")
            hours.append({"label": slot.strftime("%H:00"), "n": by_h.get(key, 0)})
    except Exception:
        hours = []
    peak = max([h["n"] for h in hours] + [1])

    top_endpoints = []
    try:
        top_endpoints = db.execute(
            """SELECT endpoint, COUNT(*) AS n FROM visits
               WHERE ts >= datetime('now', '-1 day')
               GROUP BY endpoint ORDER BY n DESC LIMIT 10""").fetchall()
    except Exception:
        pass

    samples = list(getattr(current_app, "perf_samples", []) or [])
    if samples:
        ordered = sorted(samples)
        avg_ms = sum(samples) / len(samples)
        p95_ms = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    else:
        avg_ms = p95_ms = None

    boot = current_app.config.get("STARTED_AT", "") or ""
    uptime = ""
    try:
        if boot:
            started = _dt.datetime.strptime(boot, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
            delta = _dt.datetime.now(_dt.timezone.utc) - started
            days, rem = divmod(int(delta.total_seconds()), 86400)
            hrs, rem = divmod(rem, 3600)
            mins, _ = divmod(rem, 60)
            uptime = (f"{days}d " if days else "") + f"{hrs}h {mins}m"
    except Exception:
        pass

    db_size = None
    try:
        p = Path(current_app.config.get("DATABASE", ""))
        if p.name != ":memory:" and p.exists():
            db_size = p.stat().st_size
    except Exception:
        pass

    totals = {
        "centers_live": _count("SELECT COUNT(*) FROM evacuation_centers WHERE archived=0"),
        "centers_total": _count("SELECT COUNT(*) FROM evacuation_centers"),
        "announcements_active": _count("SELECT COUNT(*) FROM announcements WHERE is_active=1 AND datetime('now') BETWEEN datetime(starts_at) AND datetime(ends_at)"),
        "announcements_total": _count("SELECT COUNT(*) FROM announcements"),
        "hotlines_live": _count("SELECT COUNT(*) FROM emergency_hotlines WHERE archived=0"),
        "admins": _count("SELECT COUNT(*) FROM administrators"),
    }
    return render_template(
        "admin/analytics.html",
        visits_24h=visits_24h, visits_1h=visits_1h, visits_5m=visits_5m,
        hours=hours, peak=peak, top_endpoints=top_endpoints,
        avg_ms=avg_ms, p95_ms=p95_ms,
        req_count=getattr(current_app, "req_count", 0),
        err_count=getattr(current_app, "err_count", 0),
        boot=boot, uptime=uptime, db_size=db_size, totals=totals,
    )
