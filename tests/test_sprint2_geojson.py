"""Sprint 2: GeoJSON evacuation-center import + NULL-capacity handling."""
import json

import pytest

from app import create_app
from scripts.import_evac_centers import (
    CITY_MAP,
    import_geojson,
    normalize_city,
    synthesize_address,
)
from utils.db import get_db, init_db
from utils.seed import seed_db


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        init_db()
        seed_db()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, app):
    # test_sprint1's lockout test poisons the shared testing DB (locks the
    # admin row); every file after it must clear that state before login.
    with app.app_context():
        db = get_db()
        db.execute("UPDATE administrators SET failed_attempts=0, locked_until=NULL")
        db.commit()
    client.post("/hanapanngbaddieguardsimarkus", data={"username": "admin", "password": "admin123"})


def _null_center(app):
    # Unique name per call: the testing DB is a shared in-memory database,
    # so rows inserted here persist across tests in the same process.
    import uuid
    tag = uuid.uuid4().hex[:8]
    with app.app_context():
        db = get_db()
        cur = db.execute(
            """INSERT INTO evacuation_centers
               (name, address, barangay, city, province, lat, lng,
                capacity, current_occupancy, source, verified)
               VALUES (?, ?, 'B1', 'Manila',
                       'Metro Manila', 14.6, 121.0, NULL, NULL, 'geojson:osm', 1)""",
            (f"Null Hall {tag}", f"1 Test St {tag}, Manila"),
        )
        db.commit()
        return cur.lastrowid


# --- pure-function unit tests (no DB) ---

def test_normalize_city_covers_all_17():
    assert len(CITY_MAP) == 17
    assert normalize_city("City of Manila") == "Manila"
    assert normalize_city("Caloocan City") == "Caloocan"
    assert normalize_city("Pateros") == "Pateros"
    assert normalize_city("Quezon City") == "Quezon City"
    assert normalize_city("City of Nowhere") is None
    assert normalize_city(None) is None
    assert normalize_city("") is None


def test_synthesize_address_disambiguates_duplicates():
    taken = set()
    a1 = synthesize_address("Gym", "B1", "Manila", "SCHOOL", taken)
    taken.add(("Gym", a1))
    a2 = synthesize_address("Gym", "B1", "Manila", "SCHOOL", taken)
    taken.add(("Gym", a2))
    a3 = synthesize_address("Gym", None, "Manila", "SCHOOL", taken)
    assert len({a1, a2}) == 2
    assert "B1" in a1 and "Manila" in a3


def test_real_file_municipalities_all_known():
    path = "data/ncr_evacuation_centers.geojson"
    try:
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        pytest.skip("dataset not present")
    raws = {f.get("properties", {}).get("municipality_input") for f in data["features"]}
    assert raws <= set(CITY_MAP), f"unmapped municipalities: {raws - set(CITY_MAP)}"


# --- importer behaviour (test DB) ---

def _write_geojson(tmp_path, features):
    p = tmp_path / "t.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection", "features": features}),
                 encoding="utf-8")
    return str(p)


def _feat(name, city="City of Manila", lon=121.0, lat=14.6, **extra):
    props = {"name": name, "barangay_input": "B1", "barangay_resolved": "B1",
             "municipality_input": city, "facility_type": "SCHOOL",
             "facility_status": "TEMPORARY", "geocode_provider": "osm",
             "confidence": 1, "verified": True, "needs_review": False,
             "review_reason": ""}
    props.update(extra)
    geom = None if lat is None else {"type": "Point", "coordinates": [lon, lat]}
    return {"type": "Feature", "geometry": geom, "properties": props}


def test_import_idempotent_and_quarantines(app, tmp_path):
    with app.app_context():
        db = get_db()
        path = _write_geojson(tmp_path, [
            _feat("A Hall"),
            _feat("A Hall", city="Quezon City"),  # same name, other city
            _feat("Ghost Hall", lat=None),        # no geometry -> staging
        ])
        s1 = import_geojson(db, path)
        assert (s1["imported"], s1["quarantined"], s1["skipped"]) == (2, 1, 0)
        n1 = db.execute("SELECT COUNT(*) c FROM evacuation_centers").fetchone()["c"]
        q1 = db.execute("SELECT * FROM staging_centers").fetchone()
        assert q1["name"] == "Ghost Hall"
        assert q1["review_reason"] == "no_coordinates"
        db.execute("UPDATE evacuation_centers SET capacity=500, current_occupancy=10 "
                   "WHERE name='A Hall' AND city='Manila'")
        db.commit()
        s2 = import_geojson(db, path)
        n2 = db.execute("SELECT COUNT(*) c FROM evacuation_centers").fetchone()["c"]
        assert n1 == n2  # no duplicates on re-import
        assert s2["updated"] == 2 and s2["imported"] == 0
        kept = db.execute("SELECT capacity, current_occupancy FROM evacuation_centers "
                          "WHERE name='A Hall' AND city='Manila'").fetchone()
        assert (kept["capacity"], kept["current_occupancy"]) == (500, 10)


def test_full_dataset_stats(app):
    path = "data/ncr_evacuation_centers.geojson"
    try:
        open(path, encoding="utf-8").close()
    except FileNotFoundError:
        pytest.skip("dataset not present")
    with app.app_context():
        stats = import_geojson(get_db(), path)
    assert stats["features"] == 868
    assert stats["imported"] == 836
    assert stats["quarantined"] == 32
    # 43 rows are flagged overall: 32 have no geometry (quarantined) and the
    # remaining 11 import live with needs_review set.
    assert stats["needs_review"] == 11
    assert stats["verified"] == 717


# --- NULL-capacity behaviour end to end ---

def test_null_capacity_api_reports_unavailable(client, app):
    cid = _null_center(app)
    rows = client.get("/api/centers").get_json()
    row = next(r for r in rows if r["id"] == cid)
    assert row["occupancy_status"] == "Status Unavailable"
    assert row["occupancy_pct"] is None and row["available_slots"] is None
    d = client.get(f"/api/centers/{cid}").get_json()
    assert d["occupancy_status"] == "Status Unavailable"
    assert client.get("/").status_code == 200
    assert client.get(f"/centers/{cid}").status_code == 200


def test_admin_update_null_capacity_requires_capacity(client, app):
    _login(client, app)
    cid = _null_center(app)
    base = {"current_occupancy": "5", "food_status": "Unknown",
            "water_status": "Unknown", "medicine_status": "Unknown",
            "hygiene_status": "Unknown", "basic_needs_status": "Unknown",
            "operational_status": "Open"}
    assert client.post(f"/admin/centers/{cid}", data=base).status_code == 400
    r = client.post(f"/admin/centers/{cid}", data={**base, "capacity": "200"})
    assert r.status_code == 302
    with app.app_context():
        c = get_db().execute(
            "SELECT capacity, current_occupancy FROM evacuation_centers WHERE id=?",
            (cid,)).fetchone()
        assert (c["capacity"], c["current_occupancy"]) == (200, 5)
    d = client.get(f"/api/centers/{cid}").get_json()
    assert d["occupancy_status"] == "Available" and d["available_slots"] == 195


def test_migration_preserves_seed_data(app):
    with app.app_context():
        db = get_db()
        cols = [c["name"] for c in db.execute("PRAGMA table_info(evacuation_centers)")]
        for col in ("source", "verified", "needs_review", "review_reason"):
            assert col in cols
        # Seed rows carry source NULL; geojson rows from other tests in this
        # process must not disturb the seed count. 'Closed Test' is excluded:
        # test_sprint1 inserts it into the same shared testing DB.
        n = db.execute("SELECT COUNT(*) c FROM evacuation_centers "
                       "WHERE archived=0 AND source IS NULL AND name != 'Closed Test'"
                       ).fetchone()["c"]
        assert n == 20
        assert db.execute("SELECT COUNT(*) c FROM evacuation_centers "
                          "WHERE archived=0 AND source IS NULL AND name != 'Closed Test' "
                          "AND capacity IS NULL"
                          ).fetchone()["c"] == 0
        kept = db.execute("SELECT capacity, verified FROM evacuation_centers "
                          "WHERE name='Marikina Sports Center'").fetchone()
        assert (kept["capacity"], kept["verified"]) == (5000, 0)

