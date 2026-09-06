"""Security regression tests: hardening headers, anonymous-API rate limits,
and XSS-safe client rendering of DB-backed strings."""
from pathlib import Path

import pytest

from app import create_app
from utils.db import init_db
from utils.seed import seed_db

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "public"


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


def test_security_headers_on_home(client):
    r = client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_security_headers_on_api(client):
    r = client.get("/api/centers")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_group_creation_rate_limited(client, app):
    # Limiter is disabled in TestingConfig; flip the shared instance on just
    # for this test, then restore so other suites are unaffected.
    app.limiter.enabled = True
    try:
        codes = [
            client.post("/api/groups", json={"name": f"SecGrp{i}"}).status_code
            for i in range(12)
        ]
    finally:
        app.limiter.enabled = False
    assert codes[:10] == [201] * 10
    assert codes[10:] == [429, 429]


def test_location_post_rate_limited(client, app):
    group = client.post("/api/groups", json={"name": "SecLocProbe"}).get_json()
    app.limiter.enabled = True
    try:
        codes = [
            client.post("/api/locations", json={
                "invite_code": group["invite_code"],
                "display_name": "SecPat",
                "lat": 14.6308,
                "lon": 121.0968,
            }).status_code
            for _ in range(61)
        ]
    finally:
        app.limiter.enabled = False
    assert codes[:60] == [201] * 60
    assert codes[60] == 429


def test_home_preview_popup_escapes_center_fields():
    src = (_TEMPLATES / "home.html").read_text(encoding="utf-8")
    assert "const esc=" in src  # escape helper defined
    assert "esc(c.name)" in src and "esc(c.city)" in src
    assert "esc(c.occupancy_status)" in src
    assert "<b>${c.name}</b>" not in src  # no raw interpolation into popup HTML


def test_quake_popup_urls_schemed_checked():
    src = (_TEMPLATES / "map.html").read_text(encoding="utf-8")
    assert "function safeUrl(" in src
    assert 'href="${q.url' not in src  # Leaflet popup must not use raw URL
    assert 'href="${esc(p.url' not in src  # escaping alone can't stop javascript:
    assert src.count("safeUrl(") >= 4  # defined once + used in all quake popups


def test_announcement_topbar_built_without_innerhtml():
    src = (Path(__file__).resolve().parent.parent / "static" / "js" / "announcements.js").read_text(encoding="utf-8")
    assert "span.innerHTML" not in src  # textContent-only construction (XSS-safe)
    assert "ann-map-bell" not in src  # no bell injected into map chrome
    assert "querySelector('.map-shell')) return;" in src  # map never covered: home tab only


def test_map_critique_fixes_present():
    src = (_TEMPLATES / "map.html").read_text(encoding="utf-8")
    assert "data-fbroute" in src  # OSM fallback keeps a Ruta-dito path
    assert "rb.style.display='none'" not in src  # Routes tab never hidden
    assert "min-height:44px" in src  # 44px touch-target floor
    assert "maybeAutoFlood" in src  # ?city= arrivals pre-select NOAH flood
    assert ".demo-banner{ display:block;" in src  # sample-data warning never hidden on phones
