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

def test_home_ok(client):
    assert client.get("/").status_code == 200

def test_map_ok(client):
    assert client.get("/map").status_code == 200

def test_directory_ok(client):
    assert client.get("/centers").status_code == 200

def test_weather_page_ok(client):
    assert client.get("/weather").status_code == 200

def test_hotlines_page_ok(client):
    assert client.get("/hotlines").status_code == 200

def test_admin_login_page_ok(client):
    assert client.get("/admin/login").status_code == 200

def test_admin_protected_redirect(client):
    assert client.get("/admin/dashboard").status_code == 302
    assert client.get("/admin/centers").status_code == 302

def test_api_centers_returns_6(client):
    r = client.get("/api/centers")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) == 6  # archived excluded
    assert "occupancy_pct" in data[0]
    assert "occupancy_status" in data[0]
    assert "available_slots" in data[0]

def test_api_hotlines_filter(client):
    r = client.get("/api/hotlines?city=Marikina")
    assert r.status_code == 200
    assert len(r.get_json()) >= 2

def test_api_weather_cached(client):
    r = client.get("/api/weather?lat=14.6308&lon=121.0968")
    assert r.status_code == 200
    assert "weather" in r.get_json()

def test_api_weather_invalid_coords(client):
    r = client.get("/api/weather?lat=999&lon=999")
    assert r.status_code == 400

def test_center_detail_ok(client):
    assert client.get("/centers/1").status_code == 200

def test_center_detail_404(client):
    assert client.get("/centers/999").status_code == 404

def test_login_invalid(client):
    r = client.post("/admin/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

def test_login_valid_and_dashboard(client):
    r = client.post("/admin/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert r.status_code == 302
    assert "/admin/dashboard" in r.headers["Location"]
    # follow login
    client.post("/admin/login", data={"username": "admin", "password": "admin123"})
    assert client.get("/admin/dashboard").status_code == 200
