"""GH issue #4: bulk-export endpoints serve a stripped public contract.

- GET /api/centers list rows exclude import-provenance internals;
  GET /api/centers/<id> keeps the full row.
- GET /api/evac-centers.geojson serves display fields only, with ETag +
  304, no-store policy, and X-Dataset-* age headers.
- Both endpoints are per-IP rate limited (limiter is off in testing, so
  the 429 tests flip the shared instance on and run last).
"""
import json

from app import create_app
from utils.db import init_db
from utils.seed import seed_db

_INTERNALS = {"notes", "source", "verified", "needs_review",
              "review_reason", "created_at"}
_GEOJSON_DROP = {"barangay_input", "confidence", "geocode_provider",
                 "geocode_query", "uncertainty_radius_m", "verified",
                 "needs_review", "review_reason"}


def _app():
    app = create_app("testing")
    with app.app_context():
        init_db()
        seed_db()
    return app


def test_centers_list_excludes_provenance_internals():
    rows = _app().test_client().get("/api/centers").get_json()
    assert isinstance(rows, list) and rows
    for row in rows:
        assert not (_INTERNALS & set(row)), f"leaked: {_INTERNALS & set(row)}"
    # display + computed fields survive the strip
    first = rows[0]
    for field in ("id", "name", "address", "city", "lat", "lng",
                  "occupancy_status", "occupancy_pct", "available_slots",
                  "location_verified", "updated_at"):
        assert field in first, f"missing display field {field}"


def test_center_detail_keeps_full_row():
    detail = _app().test_client().get("/api/centers/1").get_json()
    assert "notes" in detail  # full provenance stays on the detail route


def test_geojson_stripped_with_age_headers():
    r = _app().test_client().get("/api/evac-centers.geojson")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "no-store"
    assert r.headers.get("ETag")
    assert r.headers.get("X-Dataset-Build")
    assert r.headers.get("X-Dataset-File-Mtime")
    data = json.loads(r.data)
    assert data["type"] == "FeatureCollection" and data["features"]
    for feat in data["features"][:50]:
        props = feat["properties"]
        assert not (_GEOJSON_DROP & set(props)), f"leaked: {_GEOJSON_DROP & set(props)}"
        assert "name" in props


def test_geojson_304_on_matching_etag():
    client = _app().test_client()
    etag = client.get("/api/evac-centers.geojson").headers.get("ETag")
    assert etag
    r = client.get("/api/evac-centers.geojson",
                   headers={"If-None-Match": etag})
    assert r.status_code == 304


def test_export_endpoints_rate_limited():
    app = _app()
    client = app.test_client()
    app.limiter.enabled = True
    try:
        geo_codes = [client.get("/api/evac-centers.geojson").status_code
                     for _ in range(31)]
        assert geo_codes[-1] == 429
        list_codes = [client.get("/api/centers").status_code
                      for _ in range(121)]
        assert list_codes[-1] == 429
    finally:
        app.limiter.enabled = False
