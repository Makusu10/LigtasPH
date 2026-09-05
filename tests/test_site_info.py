import pytest
from app import create_app
from utils.db import init_db
from utils.seed import seed_db
from routes.api import site_info


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


def test_site_info_parses_import_notes():
    kind, ftype = site_info({"notes": "Sprint 2 import — capacity unreported. GYM/SPORTS FACILITY • TEMPORARY • geocoded via osm"})
    assert kind == "Temporary site — activated during disasters"
    assert ftype == "Gym/Sports Facility"
    kind, ftype = site_info({"notes": "X • PERMANENT • y"})
    assert kind == "Permanent evacuation center"
    # Real DB rows use U+00B7 MIDDLE DOT as the separator, not U+2022.
    kind, ftype = site_info({"notes": "Sprint 2 import \u2014 capacity unreported. GYM/SPORTS FACILITY \u00b7 TEMPORARY \u00b7 geocoded via osm"})
    assert kind == "Temporary site — activated during disasters"
    assert ftype == "Gym/Sports Facility"


def test_site_info_none_without_notes():
    assert site_info({"notes": None}) == (None, None)
    assert site_info({"notes": "Demo data - not verified live."}) == (None, None)
    assert site_info({}) == (None, None)


def test_api_centers_include_site_fields(client, app):
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute("DELETE FROM evacuation_centers WHERE name='SiteProbe'")
        db.execute(
            """INSERT INTO evacuation_centers
               (name, address, city, lat, lng, notes, verified)
               VALUES ('SiteProbe', 'Addr', 'Marikina', 14.6, 121.1,
                       'Sprint 2 import — capacity unreported. SCHOOL • TEMPORARY • geocoded via osm', 1)""")
        db.commit()
    try:
        rows = client.get("/api/centers?q=SiteProbe").get_json()
        assert len(rows) == 1
        r = rows[0]
        assert r["site_kind"] == "Temporary site — activated during disasters"
        assert r["facility_type"] == "School"
        assert r["location_verified"] is True
        assert r["occupancy_status"] == "Status Unavailable"  # still honest: no capacity
        d = client.get(f"/api/centers/{r['id']}").get_json()
        assert d["site_kind"] == r["site_kind"]
    finally:
        with app.app_context():
            from utils.db import get_db
            db = get_db()
            db.execute("DELETE FROM evacuation_centers WHERE name='SiteProbe'")
            db.commit()


def test_center_detail_shows_site_badges(client, app):
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute("DELETE FROM evacuation_centers WHERE name='SiteProbe2'")
        db.execute(
            """INSERT INTO evacuation_centers
               (name, address, city, lat, lng, notes, verified)
               VALUES ('SiteProbe2', 'Addr', 'Marikina', 14.6, 121.1,
                       'Sprint 2 import — capacity unreported. SCHOOL • TEMPORARY • geocoded via osm', 1)""")
        db.commit()
        cid = db.execute("SELECT id FROM evacuation_centers WHERE name='SiteProbe2'").fetchone()["id"]
    try:
        html = client.get(f"/centers/{cid}").get_data(as_text=True)
        assert "Temporary site" in html
        assert "Verified location" in html
    finally:
        with app.app_context():
            from utils.db import get_db
            db = get_db()
            db.execute("DELETE FROM evacuation_centers WHERE name='SiteProbe2'")
            db.commit()
