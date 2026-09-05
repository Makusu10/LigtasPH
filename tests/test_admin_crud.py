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
    client.post("/hanapanngbaddieguardsimarkus", data={"username": "admin", "password": "admin123"})


def test_admin_update_requires_login(client):
    r = client.post("/admin/centers/1", data={"current_occupancy": "5"})
    assert r.status_code == 302


def test_admin_update_occupancy_and_audit(client, app):
    _login(client)
    r = client.post("/admin/centers/1", data={
        "current_occupancy": "1300",
        "food_status": "Adequate",
        "water_status": "Adequate",
        "medicine_status": "Adequate",
        "hygiene_status": "Adequate",
        "basic_needs_status": "Adequate",
        "operational_status": "Open",
    })
    assert r.status_code == 302
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        c = db.execute("SELECT current_occupancy FROM evacuation_centers WHERE id=1").fetchone()
        assert c["current_occupancy"] == 1300
        audit = db.execute(
            "SELECT * FROM center_status_updates WHERE center_id=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert audit["new_occupancy"] == 1300
        assert audit["prev_occupancy"] == 1200


def test_admin_update_rejects_overflow(client):
    _login(client)
    r = client.post("/admin/centers/6", data={"current_occupancy": "99999"})
    assert r.status_code == 400


def test_admin_hotline_create_and_archive(client, app):
    _login(client)
    r = client.post("/admin/hotlines", data={
        "agency": "Test Rescue", "category": "Rescue",
        "contact_number": "143", "city": "Marikina",
    })
    assert r.status_code in (201, 302)
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        h = db.execute("SELECT * FROM emergency_hotlines WHERE agency='Test Rescue'").fetchone()
        assert h is not None
        hid = h["id"]
    r = client.post(f"/admin/hotlines/{hid}/archive", data={"action": "archive"})
    assert r.status_code == 302
    assert client.get("/api/hotlines?q=Test+Rescue").get_json() == []


def test_admin_logout_requires_post(client):
    _login(client)
    assert client.get("/admin/logout").status_code == 405
    assert client.post("/admin/logout").status_code == 302

