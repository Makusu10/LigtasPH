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


_FIRMS_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
    "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "14.6308,121.0968,320.5,0.4,0.4,2026-09-04,0600,N,VIIRS,n,1.0,290.0,5.5,D\n"
)


def test_fires_relay_fallback_when_direct_blocked(client, app, monkeypatch):
    # Restricted egress (PythonAnywhere free allowlist) blocks the direct
    # FIRMS host — the allowlisted relay must transparently take over.
    app.config["FIRMS_MAP_KEY"] = "dummy-key-for-test"
    calls = []

    def fake_fetch(url, timeout=8):
        calls.append(url)
        if "allorigins" in url:
            return _FIRMS_CSV
        raise OSError("network blocked")

    monkeypatch.setattr("services.hazards_service._fetch_text", fake_fetch)
    # Distinct coords from other tests: the shared test DB keeps cache rows
    # across tests, so reusing lat/lon would hit a stale cache entry.
    r = client.get("/api/fires?lat=14.7&lon=121.2")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "firms"
    assert body["count"] == 1
    assert body["fires"][0]["lat"] == pytest.approx(14.6308)
    assert any("firms.modaps.eosdis.nasa.gov" in u for u in calls)
    assert any("allorigins" in u for u in calls)


def test_fires_relay_failure_still_503(client, app, monkeypatch):
    app.config["FIRMS_MAP_KEY"] = "dummy-key-for-test"
    monkeypatch.setattr(
        "services.hazards_service._fetch_text",
        lambda url, timeout=8: (_ for _ in ()).throw(OSError("down")),
    )
    # Distinct coords: shared test DB keeps cache rows across tests.
    r = client.get("/api/fires?lat=14.71&lon=121.21")
    assert r.status_code == 503
    assert r.get_json().get("retry") is True


def test_fires_bad_key_skips_relay(client, app, monkeypatch):
    # A 4xx from FIRMS itself (bad key/params) fails fast: the relay would
    # fail identically, so it must not even be attempted.
    import urllib.error

    app.config["FIRMS_MAP_KEY"] = "dummy-key-for-test"
    calls = []

    def fake_fetch(url, timeout=8):
        calls.append(url)
        raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)

    monkeypatch.setattr("services.hazards_service._fetch_text", fake_fetch)
    # Distinct coords: shared test DB keeps cache rows across tests.
    r = client.get("/api/fires?lat=14.72&lon=121.22")
    assert r.status_code == 503
    assert len(calls) == 1
    assert "firms.modaps.eosdis.nasa.gov" in calls[0]
