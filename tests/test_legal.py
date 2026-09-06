"""Legal pages, honest content, and accessibility regressions (user-requested).

Covers: /privacy /terms /cookies routes + footer links, no-tracking claims,
full map attributions, labeled filter controls, keyboard support hooks,
44px target floor, and verified contrast tokens.
"""
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


def test_legal_pages_ok(client):
    for url in ("/privacy", "/terms", "/cookies"):
        r = client.get(url)
        assert r.status_code == 200, url


def test_footer_links_legal_pages(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/privacy"' in html
    assert 'href="/terms"' in html
    assert 'href="/cookies"' in html


def test_privacy_discloses_ph_law_and_practices(client):
    html = client.get("/privacy").get_data(as_text=True)
    for needle in ("Data Privacy Act", "2 hours", "30 days",
                   "no analytics", "Mapbox", "OpenStreetMap",
                   "National Privacy Commission", "Operator details"):
        assert needle in html, needle


def test_terms_disclaims_emergency_use(client):
    html = client.get("/terms").get_data(as_text=True)
    for needle in ("not an emergency service", "tel:911", "Philippines",
                   "as is", "OpenStreetMap"):
        assert needle in html, needle


def test_cookies_declares_no_tracking(client):
    html = client.get("/cookies").get_data(as_text=True)
    for needle in ("consent", "session", "no analytics", "On-device storage"):
        assert needle in html, needle


def test_no_fake_social_proof():
    paths = [ROOT / "templates" / "public" / "home.html",
             ROOT / "templates" / "public" / "map.html",
             ROOT / "templates" / "base.html"]
    for p in paths:
        low = p.read_text(encoding="utf-8").lower()
        assert "testimonial" not in low
        assert "4.8" not in low and "5 stars" not in low


def test_hero_claim_qualified():
    src = (ROOT / "templates" / "public" / "home.html").read_text(encoding="utf-8")
    assert "official evacuation centers" not in src
    assert "listed evacuation centers" in src


def test_full_map_attribution():
    for name in ("map.html", "home.html", "center_detail.html"):
        src = (ROOT / "templates" / "public" / name).read_text(encoding="utf-8")
        assert "OpenStreetMap contributors" in src, name
    assert "\u00a9 CARTO" in (ROOT / "templates" / "public" / "map.html").read_text(encoding="utf-8")


def test_filter_controls_labeled():
    d = (ROOT / "templates" / "public" / "directory.html").read_text(encoding="utf-8")
    assert 'aria-label="Search centers' in d
    assert 'aria-label="Filter by city"' in d
    h = (ROOT / "templates" / "public" / "hotlines.html").read_text(encoding="utf-8")
    assert 'aria-label="Search hotlines' in h


def test_join_button_wellformed():
    src = (ROOT / "templates" / "public" / "map.html").read_text(encoding="utf-8")
    assert "show/button" not in src
    assert ">Join" in src
    assert 'aria-label="Join group' in src


def test_keyboard_hooks_present():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "aria-expanded" in base
    assert "Escape" in base  # mobile menu Esc-to-close
    m = (ROOT / "templates" / "public" / "map.html").read_text(encoding="utf-8")
    assert "ArrowRight" in m and "ArrowLeft" in m  # tablist arrows
    a = (ROOT / "static" / "js" / "announcements.js").read_text(encoding="utf-8")
    assert "Escape" in a  # non-critical modal Esc


def test_target_and_contrast_tokens():
    css = (ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
    assert "min-height:44px" in css
    assert "--text-muted: #66707f" in css  # 5.01:1 on white
    assert "--text-muted: #9aa7bd" in css  # 6.91:1 on dark surface
    assert "color:#8a5200" in css  # 6.12:1 on cream
    assert "color:#b3261e" in css  # 6.01:1 on pink wash
    assert "background:#2e5fe0" in css  # 5.48:1 white button text
