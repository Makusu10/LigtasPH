"""Admin centers search + dark-mode contrast regressions (user-reported)."""
from pathlib import Path

import pytest

from app import create_app
from utils.db import init_db
from utils.seed import seed_db

ROOT = Path(__file__).resolve().parent.parent


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
    client.post("/hanapanngbaddieguardsimarkus",
                data={"username": "admin", "password": "admin123"})


def test_centers_search_ui_present(client):
    _login(client)
    html = client.get("/admin/centers").get_data(as_text=True)
    assert 'id="centerSearch"' in html
    assert 'id="centerCount"' in html
    assert 'id="centerRows"' in html
    assert 'id="centerNoMatch"' in html
    assert 'data-search=' in html  # rows carry name+city+id haystacks


def test_dashboard_banner_is_theme_aware(client, app):
    _login(client)
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute("DELETE FROM evacuation_centers WHERE name='Contrast Probe'")
        db.execute(
            """INSERT INTO evacuation_centers (name, address, city, lat, lng, capacity, current_occupancy)
               VALUES ('Contrast Probe', 'Addr', 'Marikina', 14.6, 121.1, NULL, NULL)""")
        db.commit()
    try:
        html = client.get("/admin/dashboard").get_data(as_text=True)
        assert "notice-warn" in html
        assert "#FFFAEB" not in html  # hardcoded cream + inherited light text
    finally:
        with app.app_context():
            from utils.db import get_db
            db = get_db()
            db.execute("DELETE FROM evacuation_centers WHERE name='Contrast Probe'")
            db.commit()


def test_contrast_css_rules():
    css = (ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
    assert "input::placeholder" in css  # explicit placeholder color (both themes)
    assert '[data-theme="dark"] .btn-primary' in css  # white text fails on periwinkle
    assert '[data-theme="dark"] .notice-warn' in css  # dark banner variant


def test_map_surfaces_themed():
    src = (ROOT / "templates" / "public" / "map.html").read_text(encoding="utf-8")
    assert src.count("background:var(--surface); color:var(--text);") >= 2  # tileFallback + navSuggest
    assert "background:rgba(255,255,255,0.95)" not in src
