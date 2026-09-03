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


def test_earthquakes_invalid_coords(client):
    assert client.get("/api/earthquakes?lat=999&lon=999").status_code == 400


def test_earthquakes_uses_cache(client, app, monkeypatch):
    # Seed a fresh cache row so no network is needed
    with app.app_context():
        from utils.db import get_db
        import json
        db = get_db()
        db.execute(
            "INSERT INTO hazards_cache (cache_key, payload) VALUES (?, ?)"
            " ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,"
            " fetched_at=datetime('now')",
            ("usgs:ph", json.dumps({"source": "usgs", "count": 1,
                                    "quakes": [{"mag": 5.1, "place": "PH",
                                                "lat": 14.6, "lon": 121.0}]})),
        )
        db.commit()
    monkeypatch.setattr(
        "services.hazards_service._fetch_text",
        lambda url, timeout=8: (_ for _ in ()).throw(AssertionError("no network")),
    )
    r = client.get("/api/earthquakes")
    assert r.status_code == 200
    assert r.get_json()["count"] == 1


def test_fires_requires_key(client, app):
    # TestingConfig has no FIRMS key -> 503, not 200 with fake data
    r = client.get("/api/fires?lat=14.6308&lon=121.0968")
    assert r.status_code == 503
    assert r.get_json().get("retry") is True


def test_fires_invalid_coords(client):
    assert client.get("/api/fires?lat=999&lon=999").status_code == 400


def test_fires_uses_cache_when_key_set(client, app, monkeypatch):
    app.config["FIRMS_MAP_KEY"] = "dummy-key-for-test"
    with app.app_context():
        from utils.db import get_db
        import json
        db = get_db()
        db.execute(
            "INSERT INTO hazards_cache (cache_key, payload) VALUES (?, ?)"
            " ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,"
            " fetched_at=datetime('now')",
            ("firms:14.63:121.1:1",
             json.dumps({"source": "firms", "count": 1, "fires": []})),
        )
        db.commit()
    monkeypatch.setattr(
        "services.hazards_service._fetch_text",
        lambda url, timeout=8: (_ for _ in ()).throw(AssertionError("no network")),
    )
    r = client.get("/api/fires?lat=14.6308&lon=121.0968")
    assert r.status_code == 200
