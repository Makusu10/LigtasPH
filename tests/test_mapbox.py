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

def test_map_without_token_uses_osm_fallback(client, app):
    app.config["MAPBOX_TOKEN"] = ""
    r = client.get("/map")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "unpkg.com/leaflet" in html
    assert "mapbox-gl.js" not in html
    assert 'id="gpsBox"' not in html  # GPS panel only rendered with token
    assert "isolation:isolate" in html or "isolation: isolate" in html
    # Tile-fallback message element always rendered
    assert 'id="tileFallback"' in html
    # CartoDB fallback URL wired in Leaflet fallback
    assert "cartocdn.com" in html
    assert "tileerror" in html
    assert "switchedToCarto" in html

def test_map_with_token_uses_mapbox(client, app):
    app.config["MAPBOX_TOKEN"] = "pk.test-token"
    r = client.get("/map")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "mapbox-gl.js" in html
    assert 'leaflet-heat.js" crossorigin' not in html  # no static Leaflet tags (only dynamic fallback strings)
    assert 'leaflet.js" integrity' not in html
    assert "pk.test-token" in html
    assert 'id="gpsBox"' in html
    assert "maxZoom" in html  # initial fit capped so tiles fill the viewport
    assert "fadeDuration" in html
    for el in ['id="navDest"', 'id="navSuggest"', 'id="navOrigin"', 'id="navModes"',
               'id="navGo"', 'id="followBtn"', 'id="navSteps"']:
        assert el in html
    for el in ['id="sidePanel"', 'id="panelOpen"', 'id="panelClose"', 'map-fullbleed', 'map-shell']:
        assert el in html
    assert 'id="gpsStatus"' in html  # integrated-GPS status line
    assert 'id="mapMode"' in html  # engine mode badge
    assert 'mapboxgl-ctrl-geolocate' in html  # native-control visibility guard
    assert 'LocateCtl' in html or 'Use my location' in html  # fallback locate control
    assert 'queryRenderedFeatures' in html  # POI tap lookup
    assert 'hz-quakes-layer' in html and 'hz-fires-layer' in html
    # Mapbox error handler for invalid-token / tile failures
    assert "map.on('error'" in html or 'map.on("error"' in html
    assert 'id="tileFallback"' in html

def test_home_and_detail_render_with_token(client, app):
    app.config["MAPBOX_TOKEN"] = "pk.test-token"
    assert client.get("/").status_code == 200
    assert client.get("/centers/1").status_code == 200
    assert client.get("/centers/1").get_data(as_text=True).count("mapbox-gl.js") == 1

def test_config_reads_mapbox_token_env(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", "pk.from-env")
    from config import BaseConfig
    # BaseConfig binds at import; check factory propagation instead
    app = create_app("testing")
    assert app.config["MAPBOX_TOKEN"] == "pk.from-env"

def test_dynamic_pages_send_no_cache(client):
    # Phones heuristic-cache headerless HTML/JSON and hide new tabs (Group).
    for path in ("/", "/map", "/api/centers"):
        r = client.get(path)
        assert r.status_code == 200
        cc = r.headers.get("Cache-Control", "")
        assert "no-store" in cc, f"{path} missing no-store: {cc!r}"
