"""Hazard proxies for LigtasPH — USGS earthquakes (keyless) + NASA FIRMS fires (keyed).

Contract mirrors weather/air-quality services: fresh cache -> provider ->
stale cache -> (None, err) so routes return 503 with retry:true. Never fabricates.
"""

from __future__ import annotations

import csv
import io
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import current_app

USGS_FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
FIRMS_AREA_TMPL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{ver}/{key}/{src}/"
    "{west}/{south}/{east}/{north}/{days}"
)
FIRMS_VERSION = "1"
FIRMS_SOURCE = "VIIRS_SNPP_NRT"

QUAKE_TTL = 5 * 60
QUAKE_STALE_TTL = 60 * 60
FIRE_TTL = 30 * 60
FIRE_STALE_TTL = 3 * 60 * 60
REQ_TIMEOUT = 8
MAX_BYTES = 2_000_000

# PH bounding box fallback when no center given
PH_BBOX = (116.0, 4.0, 127.0, 22.0)


def _fetch_text(url: str, timeout: int = REQ_TIMEOUT) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "LigtasPH/1.0 (hazards proxy)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Provider response too large")
    return raw.decode("utf-8", errors="replace")


def _haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6371.0
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(a_lat))
        * math.cos(math.radians(b_lat))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(h))


def _cache_get(db, key: str, max_age: int) -> dict | None:
    try:
        row = db.execute(
            "SELECT payload, (julianday('now') - julianday(fetched_at))*86400 AS age"
            " FROM hazards_cache WHERE cache_key=?",
            (key,),
        ).fetchone()
        if not row:
            return None
        if row["age"] is None or float(row["age"]) > max_age:
            return None
        payload = json.loads(row["payload"])
        if isinstance(payload, dict):
            payload["_cached"] = True
            return payload
        return None
    except Exception as exc:
        current_app.logger.warning("hazards cache read failed: %s", exc)
        return None


def _cache_set(db, key: str, payload: dict) -> None:
    try:
        db.execute(
            "INSERT INTO hazards_cache (cache_key, payload) VALUES (?, ?)"
            " ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,"
            " fetched_at=datetime('now')",
            (key, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
        )
        db.commit()
    except Exception as exc:
        current_app.logger.warning("hazards cache write failed: %s", exc)


def _parse_usgs(feed: dict, lat: float | None, lon: float | None,
                radius_km: float | None) -> list[dict]:
    out: list[dict] = []
    for feat in (feed.get("features") or []):
        try:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            flon, flat = float(coords[0]), float(coords[1])
            depth = float(coords[2]) if len(coords) > 2 else None
            if lat is not None and lon is not None and radius_km:
                if _haversine_km(lat, lon, flat, flon) > radius_km:
                    continue
            elif lat is None:
                # default PH view
                w, s, e, n = PH_BBOX
                if not (s <= flat <= n and w <= flon <= e):
                    continue
            out.append({
                "mag": props.get("mag"),
                "place": props.get("place"),
                "time": props.get("time"),
                "lat": flat,
                "lon": flon,
                "depth_km": depth,
                "url": props.get("url"),
            })
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda q: (q.get("mag") or 0), reverse=True)
    return out[:200]


def fetch_earthquakes(db, lat: float | None = None, lon: float | None = None,
                       radius_km: float = 500) -> tuple[dict | None, str | None]:
    key = f"usgs:{lat}:{lon}:{radius_km}" if lat is not None else "usgs:ph"
    fresh = _cache_get(db, key, QUAKE_TTL)
    if fresh is not None:
        return fresh, None
    try:
        raw = _fetch_text(USGS_FEED)
        feed = json.loads(raw)
        quakes = _parse_usgs(feed, lat, lon, radius_km)
        payload = {
            "source": "usgs",
            "count": len(quakes),
            "quakes": quakes,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _cache_set(db, key, payload)
        return payload, None
    except Exception as exc:
        current_app.logger.warning("USGS request failed: %s", exc)
        stale = _cache_get(db, key, QUAKE_STALE_TTL)
        if stale is not None:
            stale = dict(stale)
            stale["_stale"] = True
            return stale, None
        return None, "Earthquake data is currently unavailable for this location."


def _parse_firms_csv(text: str, limit: int = 500) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    out: list[dict] = []
    for row in reader:
        try:
            out.append({
                "lat": float(row.get("latitude")),
                "lon": float(row.get("longitude")),
                "brightness": float(row.get("bright_ti4") or 0),
                "confidence": (row.get("confidence") or "").strip(),
                "date": row.get("acq_date"),
                "time": row.get("acq_time"),
            })
        except (TypeError, ValueError):
            continue
        if len(out) >= limit:
            break
    return out


def fetch_fires(db, lat: float = 14.6308, lon: float = 121.0968,
                days: int = 1) -> tuple[dict | None, str | None]:
    map_key = str(current_app.config.get("FIRMS_MAP_KEY", "")).strip()
    if not map_key or map_key == "YOUR_FIRMS_MAP_KEY":
        return None, "Fire data is not configured (missing FIRMS key)."
    days = max(1, min(int(days or 1), 2))
    # ~2deg box around center, clamped to PH region
    west, east = max(116.0, lon - 2), min(127.0, lon + 2)
    south, north = max(4.0, lat - 2), min(22.0, lat + 2)
    key = f"firms:{round(lat,2)}:{round(lon,2)}:{days}"
    fresh = _cache_get(db, key, FIRE_TTL)
    if fresh is not None:
        return fresh, None
    try:
        url = FIRMS_AREA_TMPL.format(
            ver=FIRMS_VERSION, key=urllib.parse.quote(map_key, safe=""),
            src=FIRMS_SOURCE, west=west, south=south, east=east,
            north=north, days=days,
        )
        text = _fetch_text(url)
        if text.lstrip().startswith(("Invalid", "Error", "<")):
            raise ValueError("FIRMS rejected the request")
        fires = _parse_firms_csv(text)
        payload = {
            "source": "firms",
            "provider": FIRMS_SOURCE,
            "count": len(fires),
            "fires": fires,
            "bbox": [west, south, east, north],
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _cache_set(db, key, payload)
        return payload, None
    except Exception as exc:
        current_app.logger.warning("FIRMS request failed: %s", exc)
        stale = _cache_get(db, key, FIRE_STALE_TTL)
        if stale is not None:
            stale = dict(stale)
            stale["_stale"] = True
            return stale, None
        return None, "Fire data is currently unavailable for this location."
