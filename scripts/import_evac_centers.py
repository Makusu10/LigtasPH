"""Sprint 2 importer: NCR evacuation-centers GeoJSON -> SQLite.

Build-time/offline tool (like scripts/convert_noah.py) plus a thin
`flask --app app import-geojson` wrapper in app.py. Stdlib only.

Usage:
    .venv/bin/python scripts/import_evac_centers.py data/ncr_evacuation_centers.geojson
    .venv/bin/python -m flask --app app import-geojson [path]

Mapping decisions (see Sprint 2 report):
- GeoJSON coords are [lon, lat]; DB stores lat/lng. Range-asserted.
- `municipality_input` ("City of Manila") is normalized via CITY_MAP to the
  short names the seed and /api/ncr-lgus use ("Manila"). Unknown values are
  quarantined, never guessed.
- The file has no street address; address is synthesized as
  "<name>, <barangay>, <city>" with a facility-type suffix on collision, so
  UNIQUE(name, address) holds even for the 56 repeated names.
- capacity/current_occupancy import as NULL (unknown until an admin sets
  real numbers); those rows read "Status Unavailable" everywhere.
- Re-imports only refresh geocoded fields (coords, flags, notes). Admin-set
  capacity, occupancy, supplies, status, and contacts are never clobbered.
- Features without usable Point geometry go to staging_centers, which is
  rebuilt from scratch on every import (fresh quarantine snapshot).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "data" / "ncr_evacuation_centers.geojson"

# municipality_input -> city label used by seed_db() and /api/ncr-lgus.
CITY_MAP = {
    "City of Manila": "Manila",
    "Pasay City": "Pasay",
    "City of Parañaque": "Parañaque",
    "City of Pasig": "Pasig",
    "Quezon City": "Quezon City",
    "City of Navotas": "Navotas",
    "City of Makati": "Makati",
    "City of Las Piñas": "Las Piñas",
    "Caloocan City": "Caloocan",
    "City of Mandaluyong": "Mandaluyong",
    "City of Muntinlupa": "Muntinlupa",
    "Taguig City": "Taguig",
    "City of Malabon": "Malabon",
    "City of San Juan": "San Juan",
    "Pateros": "Pateros",
    "City of Marikina": "Marikina",
    "City of Valenzuela": "Valenzuela",
}


def normalize_city(raw) -> str | None:
    """Map a GeoJSON municipality_input to the DB city label, or None."""
    if raw is None:
        return None
    return CITY_MAP.get(str(raw).strip())


def synthesize_address(name, barangay, city, facility_type, taken) -> str:
    """First-fit UNIQUE(name, address)-safe address against `taken`.

    Kept for one-off use; the batch importer uses plan_addresses() instead,
    which is deterministic across runs (this one depends on `taken` order).
    """
    base = f"{name}, {barangay}, {city}" if barangay else f"{name}, {city}"
    candidate = base
    if (name, candidate) not in taken:
        return candidate
    candidate = f"{base} ({facility_type or 'facility'})"
    if (name, candidate) not in taken:
        return candidate
    n = 2
    while (name, f"{candidate} #{n}") in taken:
        n += 1
    return f"{candidate} #{n}"


def plan_addresses(items) -> dict:
    """Deterministic (name -> address) plan for one import batch.

    items: list of (idx, name, barangay, city, facility_type, lon, lat).
    Features sharing a (name, base address) are disambiguated by stable
    sort order, so re-imports reproduce identical addresses and hit the
    UPDATE path instead of duplicating rows.
    """
    groups = {}
    for item in items:
        idx, name, barangay, city, ftype, lon, lat = item
        base = f"{name}, {barangay}, {city}" if barangay else f"{name}, {city}"
        groups.setdefault((name, base), []).append(item)
    planned = {}
    for (name, base), members in groups.items():
        members.sort(key=lambda m: (m[4] or "", m[5], m[6]))
        for j, m in enumerate(members):
            if j == 0:
                planned[m[0]] = base
            elif j == 1:
                planned[m[0]] = f"{base} ({m[4] or 'facility'})"
            else:
                planned[m[0]] = f"{base} ({m[4] or 'facility'}) #{j}"
    return planned


def _valid_point(geom):
    """Return (lat, lng) for a usable Point, else None. Never swaps."""
    if not isinstance(geom, dict) or geom.get("type") != "Point":
        return None
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        return None
    try:
        lon, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _provenance_note(props) -> str:
    bits = [
        props.get("facility_type") or "facility",
        props.get("facility_status") or "status unknown",
        f"geocoded via {props.get('geocode_provider') or 'unknown'}",
    ]
    if props.get("confidence") is not None:
        bits.append(f"conf {props.get('confidence')}")
    if props.get("uncertainty_radius_m") is not None:
        bits.append(f"±{props.get('uncertainty_radius_m')}m")
    if props.get("triangulated"):
        bits.append("triangulated")
    if props.get("geocode_query"):
        bits.append(f"query: {props.get('geocode_query')}")
    return "Sprint 2 import — capacity unreported. " + " · ".join(bits)


def import_geojson(db, path) -> dict:
    """Load features into evacuation_centers / staging_centers. Returns stats."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features") or []
    stats = {"features": len(features), "imported": 0, "updated": 0,
             "quarantined": 0, "skipped": 0, "needs_review": 0, "verified": 0}
    db.execute("DELETE FROM staging_centers")

    # Pass 1: validate. Bad rows are quarantined; valid rows are collected
    # for deterministic address planning in pass 2.
    valid = []
    for idx, feat in enumerate(features):
        props = feat.get("properties") or {}
        name = (props.get("name") or "").strip()
        if not name:
            stats["skipped"] += 1
            continue
        city = normalize_city(props.get("municipality_input"))
        barangay = (props.get("barangay_resolved")
                    or props.get("barangay_input") or "").strip() or None
        point = _valid_point(feat.get("geometry"))
        if city is None or point is None:
            reason = (props.get("review_reason") or "").strip() or (
                "unknown_city" if city is None else "no_coordinates")
            db.execute(
                """INSERT INTO staging_centers
                   (name, barangay, city, facility_type, facility_status,
                    source, confidence, review_reason, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (name, barangay, (props.get("municipality_input") or "").strip() or None,
                 props.get("facility_type"), props.get("facility_status"),
                 f"geojson:{props.get('geocode_provider') or 'unknown'}",
                 props.get("confidence"), reason,
                 json.dumps(feat, ensure_ascii=False)),
            )
            stats["quarantined"] += 1
            continue
        lat, lng = point
        valid.append((idx, feat, props, name, barangay, city, lat, lng))

    addresses = plan_addresses(
        [(idx, name, barangay, city, (props.get("facility_type") or ""),
          lng, lat)
         for idx, feat, props, name, barangay, city, lat, lng in valid])

    # Pass 2: idempotent upsert on (name, address).
    for idx, feat, props, name, barangay, city, lat, lng in valid:
        address = addresses[idx]
        row = db.execute(
            "SELECT id, source FROM evacuation_centers WHERE name=? AND address=?",
            (name, address)).fetchone()
        if row and row["source"] and not str(row["source"]).startswith("geojson"):
            # A non-imported row owns this key (e.g. a demo seed): fall back
            # deterministically instead of clobbering it.
            address = f"{address} (imported)"
            row = db.execute(
                "SELECT id, source FROM evacuation_centers WHERE name=? AND address=?",
                (name, address)).fetchone()
        verified = 1 if props.get("verified") else 0
        needs_review = 1 if props.get("needs_review") else 0
        review_reason = (props.get("review_reason") or "").strip() or None
        note = _provenance_note(props)[:2000]
        provider = f"geojson:{props.get('geocode_provider') or 'unknown'}"
        municipality = (props.get("municipality_input") or "").strip() or None
        if row:
            # Refresh geocoded fields only — never clobber admin-set numbers.
            db.execute(
                """UPDATE evacuation_centers SET barangay=?, city=?, municipality=?,
                   province='Metro Manila', lat=?, lng=?, source=?, verified=?,
                   needs_review=?, review_reason=?, notes=?,
                   updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=?""",
                (barangay, city, municipality, lat, lng, provider,
                 verified, needs_review, review_reason, note, row["id"]),
            )
            stats["updated"] += 1
        else:
            db.execute(
                """INSERT INTO evacuation_centers
                   (name, address, barangay, city, municipality, province,
                    lat, lng, capacity, current_occupancy, operational_status,
                    contact_number, notes, source, verified, needs_review, review_reason)
                   VALUES (?,?,?,?,?, 'Metro Manila',?,?, NULL, NULL, 'Open',
                           NULL,?,?,?,?,?)""",
                (name, address, barangay, city, municipality, lat, lng, note,
                 provider, verified, needs_review, review_reason),
            )
            stats["imported"] += 1
        stats["verified"] += verified
        stats["needs_review"] += needs_review
    db.commit()
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=str(DEFAULT_PATH),
                    help="GeoJSON FeatureCollection to import")
    args = ap.parse_args(argv)
    import sys
    sys.path.insert(0, str(ROOT))
    from app import create_app  # noqa: E402
    app = create_app()
    with app.app_context():
        from utils.db import get_db  # noqa: E402
        stats = import_geojson(get_db(), args.path)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
