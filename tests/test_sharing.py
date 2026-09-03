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


def _create_group(client, name="Family"):
    r = client.post("/api/groups", json={"name": name})
    assert r.status_code == 201
    return r.get_json()


def test_create_group_returns_invite_code(client):
    body = _create_group(client)
    assert body["invite_code"]
    assert len(body["invite_code"]) >= 6
    assert body["name"] == "Family"


def test_post_location_roundtrip(client):
    group = _create_group(client)
    r = client.post("/api/locations", json={
        "invite_code": group["invite_code"],
        "display_name": "Ana",
        "lat": 14.6308,
        "lon": 121.0968,
    })
    assert r.status_code == 201
    assert "expires_at" in r.get_json()

    r = client.get(f"/api/groups/{group['invite_code']}/locations")
    assert r.status_code == 200
    rows = r.get_json()
    assert len(rows) == 1
    assert rows[0]["display_name"] == "Ana"
    assert rows[0]["lat"] == pytest.approx(14.6308)
    assert rows[0]["lon"] == pytest.approx(121.0968)


def test_post_location_invalid_coords(client):
    group = _create_group(client)
    r = client.post("/api/locations", json={
        "invite_code": group["invite_code"],
        "display_name": "Ana",
        "lat": 999,
        "lon": 999,
    })
    assert r.status_code == 400


def test_post_location_unknown_group(client):
    r = client.post("/api/locations", json={
        "invite_code": "NOPE01",
        "display_name": "Ana",
        "lat": 14.6,
        "lon": 121.0,
    })
    assert r.status_code == 404


def test_get_locations_unknown_group(client):
    assert client.get("/api/groups/NOPE01/locations").status_code == 404


def test_expired_locations_hidden(client, app):
    group = _create_group(client)
    client.post("/api/locations", json={
        "invite_code": group["invite_code"],
        "display_name": "Old",
        "lat": 14.6,
        "lon": 121.0,
    })
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute(
            "UPDATE live_locations SET expires_at = datetime('now', '-1 hour')"
        )
        db.commit()
    rows = client.get(f"/api/groups/{group['invite_code']}/locations").get_json()
    assert rows == []
