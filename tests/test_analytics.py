import pytest
from app import create_app
from utils.db import init_db, get_db
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


def _visits(app):
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM visits").fetchone()[0]


def _login(client):
    client.post("/admin/login", data={"username": "admin", "password": "admin123"})


def test_analytics_requires_login(client):
    assert client.get("/admin/analytics").status_code == 302


def test_page_views_are_tracked(client, app):
    before = _visits(app)
    assert client.get("/").status_code == 200
    assert client.get("/map").status_code == 200
    assert _visits(app) == before + 2


def test_static_assets_not_tracked(client, app):
    before = _visits(app)
    client.get("/static/css/main.css")
    assert _visits(app) == before


def test_analytics_page_renders(client, app):
    _login(client)
    client.get("/")
    r = client.get("/admin/analytics")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Visits · 24h" in html
    assert "Uptime" in html
    assert "Top pages" in html
    assert "Content totals" in html
    assert "public.home" in html  # endpoint breakdown lists visited pages
