import pytest
from app import create_app
from utils.db import init_db
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


def _login(client):
    r = client.post("/hanapanngbaddieguardsimarkus", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 302


def test_centers_version_shape(client):
    r = client.get("/api/centers/version")
    assert r.status_code == 200
    v = r.get_json()
    assert v["count"] == 20
    assert isinstance(v["max_updated_at"], str) and v["max_updated_at"]


def test_centers_version_bumps_after_admin_update(client):
    before = client.get("/api/centers/version").get_json()
    _login(client)
    try:
        r = client.post("/admin/centers/1", data={
            "current_occupancy": "1300",
            "food_status": "Adequate", "water_status": "Adequate",
            "medicine_status": "Adequate", "hygiene_status": "Adequate",
            "basic_needs_status": "Adequate", "operational_status": "Open",
            "contact_number": "(02) 8646-1631", "notes": "live test",
        })
        assert r.status_code in (200, 302)
        after = client.get("/api/centers/version").get_json()
        assert after != before
        detail = client.get("/api/centers/1").get_json()
        assert detail["current_occupancy"] == 1300
    finally:
        # Restore seed occupancy: shared in-memory test DB persists
        # across test modules and seed_db() skips non-empty tables.
        client.post("/admin/centers/1", data={
            "current_occupancy": "1200",
            "food_status": "Adequate", "water_status": "Adequate",
            "medicine_status": "Adequate", "hygiene_status": "Adequate",
            "basic_needs_status": "Adequate", "operational_status": "Open",
            "contact_number": "(02) 8646-1631", "notes": "Demo data - not verified live. Main evacuation hub.",
        })


def test_centers_version_count_drops_after_archive(client):
    _login(client)
    try:
        r = client.post("/admin/centers/1/archive", data={"action": "archive"})
        assert r.status_code in (200, 302)
        v = client.get("/api/centers/version").get_json()
        assert v["count"] == 19
        assert len(client.get("/api/centers").get_json()) == 19
        assert client.get("/api/centers/1").status_code == 404
    finally:
        # Shared in-memory test DB persists across test modules and
        # seed_db() skips non-empty tables, so restore center 1.
        client.post("/admin/centers/1/archive", data={"action": "unarchive"})
    v = client.get("/api/centers/version").get_json()
    assert v["count"] == 20

