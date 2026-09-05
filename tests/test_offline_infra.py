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


def test_sw_served_as_javascript(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.content_type
    assert "caches.open" in r.get_data(as_text=True)


def test_map_registers_sw(client):
    assert "/sw.js" in client.get("/map").get_data(as_text=True)


def test_static_assets_cache_busted(client):
    html = client.get("/").get_data(as_text=True)
    assert "main.css?v=" in html
    assert "prefs.js?v=" in html


def test_evac_geojson_endpoint(client):
    r = client.get("/api/evac-centers.geojson")
    assert r.status_code == 200
    assert "geo+json" in r.content_type
    data = r.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 800


def test_center_status_endpoint(client):
    assert client.get("/api/centers/999999/status").status_code == 404
    r = client.get("/api/centers/1/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "not_available"
    assert data["available"] is False
