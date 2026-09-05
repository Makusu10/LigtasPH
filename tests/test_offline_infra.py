import shutil
import subprocess
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


def test_sw_version_tied_to_build(client, app):
    r = client.get("/sw.js")
    body = r.get_data(as_text=True)
    build_id = app.config.get("STARTED_AT", "")
    assert build_id and build_id in body  # GH #5: version retires per deploy
    assert "ligtasph-sw-v1" not in body  # hardcoded version is gone
    assert "__BUILD_ID__" not in body  # placeholder always substituted
    assert r.headers.get("Cache-Control") == "no-store"  # never pin the SW


def test_map_stale_banner_present(client):
    html = client.get("/map").get_data(as_text=True)
    assert 'id="staleBanner"' in html
    assert 'role="alert"' in html
    assert "updateStaleBanner" in html
    assert "ligtasph_data_age_v1" in html
    assert "DRRMO" in html
    # banner text is set via textContent (XSS-safe), never innerHTML
    assert ".textContent='You are offline" in html \
        or 'textContent="You are offline' in html \
        or "textContent='You are offline" in html


def test_precached_geojson_carries_provenance_headers(client):
    # The SW install gate refuses bodies without these (GH #5); the
    # endpoint must therefore always emit them (GH #4/#7).
    r = client.get("/api/evac-centers.geojson")
    assert r.headers.get("ETag")
    assert r.headers.get("X-Dataset-Sha256")
    assert r.headers.get("X-Dataset-Build")
    assert r.headers.get("X-Dataset-File-Mtime")


def _extract_banner_fn():
    src = (_TEMPLATES / "map.html").read_text(encoding="utf-8")
    i = src.index("function updateStaleBanner()")
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    raise AssertionError("updateStaleBanner() not found")


@pytest.mark.skipif(shutil.which("node") is None, reason="node required for JS drill")
def test_stale_banner_logic_offline_dated_online_hidden():
    # Behavioral drill on the shipped banner function: offline shows a
    # dated DRRMO warning, online hides it. (Node >= 21 ships its own
    # global navigator, so the harness overrides it via defineProperty.)
    template = _extract_banner_fn() + """
const seen = {};
Object.defineProperty(globalThis, 'navigator', { value: { onLine: OFFLINE_FLAG }, configurable: true, writable: true });
globalThis.document = { getElementById: (id) => {
  if (id === 'staleBanner') return { style: { set display(v){ seen.display = v; } } };
  if (id === 'staleBannerText') return { set textContent(v){ seen.text = v; } };
  return null;
}};
globalThis.localStorage = { getItem: () => JSON.stringify({at: 1785892800000}) };
globalThis.window = {};
updateStaleBanner();
console.log(JSON.stringify(seen));
"""
    offline_text = ""
    for offline, want_display in (("false", "block"), ("true", "none")):
        probe = template.replace("OFFLINE_FLAG", offline)
        r = subprocess.run(["node", "-e", probe], capture_output=True,
                           text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        import json
        seen = json.loads(r.stdout)
        assert seen.get("display") == want_display
        if offline == "false":
            offline_text = seen.get("text", "")
    assert "DRRMO" in offline_text and "PHT" in offline_text


def test_center_status_endpoint(client):
    assert client.get("/api/centers/999999/status").status_code == 404
    r = client.get("/api/centers/1/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "not_available"
    assert data["available"] is False
