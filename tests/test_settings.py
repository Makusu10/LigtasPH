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


def test_settings_page_ok(client):
    r = client.get("/settings")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "js/settings.js" in html
    assert "ligtasph_theme" in html  # pre-paint theme snippet


def test_api_status_flags_no_secrets(client, app):
    app.config["OPENWEATHER_API_KEY"] = "sk-test-sentinel-abcdef1234"
    app.config["MAPBOX_TOKEN"] = "pk.test-sentinel"
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "sk-test-sentinel-abcdef1234" not in body
    assert "pk.test-sentinel" not in body
    data = r.get_json()
    assert data["providers"]["openweather"] is True
    assert data["providers"]["mapbox"] is True
    assert data["providers"]["open_meteo"] is True
    assert data["build_id"]  # clients use this to refresh caches


def test_admin_keys_requires_login(client):
    assert client.get("/admin/keys").status_code == 302


def test_admin_keys_masked_and_save(client, app, monkeypatch):
    _login(client)
    app.config["OPENWEATHER_API_KEY"] = "ow-secret-9999"
    r = client.get("/admin/keys")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "ow-secret-9999" not in html  # masked only
    assert "9999" in html  # last-4 tail shown

    saved = {}

    def fake_save(updates):
        saved.update(updates)
        return ["OPENWEATHER_API_KEY"]

    monkeypatch.setattr("utils.envkeys.save", fake_save)
    r = client.post("/admin/keys", data={"OPENWEATHER_API_KEY": "ow-new-key"})
    assert r.status_code == 302
    assert saved.get("OPENWEATHER_API_KEY") == "ow-new-key"
    assert app.config["OPENWEATHER_API_KEY"] == "ow-new-key"  # applied live


def test_admin_keys_empty_keeps_current(client, app, monkeypatch):
    _login(client)
    app.config["OPENWEATHER_API_KEY"] = "ow-keep-me"

    def fake_save(updates):
        assert updates.get("OPENWEATHER_API_KEY") in ("", None)
        return []

    monkeypatch.setattr("utils.envkeys.save", fake_save)
    assert client.post("/admin/keys", data={"OPENWEATHER_API_KEY": ""}).status_code == 302
    assert app.config["OPENWEATHER_API_KEY"] == "ow-keep-me"


def test_admin_restart_refused_under_gunicorn(client, monkeypatch):
    _login(client)
    monkeypatch.setenv("SERVER_SOFTWARE", "gunicorn/21.2.0")
    r = client.post("/admin/restart")
    assert r.status_code == 302  # redirected with warning, no restart


def test_admin_restart_requires_login(client):
    assert client.post("/admin/restart").status_code == 302

