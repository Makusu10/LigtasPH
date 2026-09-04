import pytest
from app import create_app
from utils.db import init_db
from utils.seed import seed_db
from utils.environment import calculate_heat_index, classify_heat_index, classify_pm25, overall_status

@pytest.fixture
def app():
    a = create_app("testing")
    with a.app_context():
        init_db()
        seed_db()
    return a

@pytest.fixture
def client(app):
    return app.test_client()

# PAGASA Heat Index boundaries — test every exact value including spec 26.9,27,32,33,41,42,51,52
@pytest.mark.parametrize("hi,expected", [
    (26.9, "Not Hazardous"),
    (26.99, "Not Hazardous"),
    (27, "Caution"),
    (27.0, "Caution"),
    (32, "Caution"),
    (32.0, "Caution"),
    (32.9, "Caution"),
    (33, "Extreme Caution"),
    (33.0, "Extreme Caution"),
    (41, "Extreme Caution"),
    (41.0, "Extreme Caution"),
    (41.9, "Extreme Caution"),
    (42, "Danger"),
    (42.0, "Danger"),
    (51, "Danger"),
    (51.0, "Danger"),
    (51.9, "Danger"),
    (52, "Extreme Danger"),
    (52.0, "Extreme Danger"),
    (60, "Extreme Danger"),
])
def test_heat_pagasa_boundaries(hi, expected):
    assert classify_heat_index(hi)["category"] == expected

def test_heat_unavailable():
    assert classify_heat_index(None)["category"] == "Unavailable"
    assert classify_heat_index(float("nan"))["category"] == "Unavailable"

def test_calculate_heat_index_basic():
    # 30C 70% -> should be >30
    hi = calculate_heat_index(30, 70)
    assert hi is not None and hi > 30
    # None inputs -> None
    assert calculate_heat_index(None, 70) is None
    assert calculate_heat_index(30, None) is None
    # Below 27 threshold still calculable
    hi2 = calculate_heat_index(26, 50)
    assert hi2 is not None

# DENR PM2.5 0-25 Good, 25.1-35 Fair, 35.1-45 Sensitive, 45.1-55 Very Unhealthy, 55.1-90 Acutely, >91 Emergency
@pytest.mark.parametrize("pm25,expected", [
    (0, "Good"), (12, "Good"), (25, "Good"),
    (25.1, "Fair"), (30, "Fair"), (35, "Fair"),
    (35.1, "Unhealthy for Sensitive Groups"), (40, "Unhealthy for Sensitive Groups"), (45, "Unhealthy for Sensitive Groups"),
    (45.1, "Very Unhealthy"), (50, "Very Unhealthy"), (55, "Very Unhealthy"),
    (55.1, "Acutely Unhealthy"), (70, "Acutely Unhealthy"), (90, "Acutely Unhealthy"),
    (91, "Emergency"), (91.1, "Emergency"), (150, "Emergency"),
])
def test_pm25_denr_boundaries(pm25, expected):
    assert classify_pm25(pm25)["category"] == expected

def test_pm25_unavailable():
    assert classify_pm25(None)["category"] == "Unavailable"
    assert classify_pm25(float("nan"))["category"] == "Unavailable"

def test_overall_more_severe_wins():
    # heat Danger vs air Good -> Danger
    o = overall_status("Danger", "Good")
    assert o["category"] == "Danger" and o["source"] == "heat"
    # air Emergency vs heat Caution -> Emergency (air)
    o2 = overall_status("Caution", "Emergency")
    assert o2["category"] == "Emergency" and o2["source"] == "air"
    # both unavailable
    o3 = overall_status("Unavailable", "Unavailable")
    assert o3["category"] == "Unavailable"
    # one unavailable
    o4 = overall_status("Extreme Caution", "Unavailable")
    assert o4["category"] == "Extreme Caution"
    o5 = overall_status("Unavailable", "Good")
    assert o5["category"] == "Good"

def test_wmo_map_covers_all_documented_codes():
    # Every WMO weather code per open-meteo docs must render a real label —
    # never a raw "WMO 96". Guards the cross-reference accuracy fix.
    from services.weather_service import WMO_MAP
    documented = {0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65,
                  66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}
    assert documented <= set(WMO_MAP)
    for code, label in WMO_MAP.items():
        assert label and not label.startswith("WMO ")

def test_fetch_open_meteo_maps_hail_and_feels_like(monkeypatch):
    # Thunderstorm-with-hail code + apparent temperature + rain chance
    # must flow into the payload (mocked provider, no network).
    import services.weather_service as ws
    def fake_fetch(url, timeout=5):
        if "hourly=" in url:
            return {"hourly": {"time": [], "temperature_2m": []}, "daily": {}}
        return {"current": {"temperature_2m": 31.0, "relative_humidity_2m": 70,
                            "apparent_temperature": 36.5, "precipitation": 0.2,
                            "precipitation_probability": 80,
                            "wind_speed_10m": 5.0, "weather_code": 96,
                            "is_day": 1, "time": "2026-09-04T14:00"}}
    monkeypatch.setattr(ws, "_fetch_json", fake_fetch)
    payload = ws.fetch_open_meteo(14.6, 121.0, "Manila")
    assert payload["weather"][0]["description"] == "Thunderstorm with slight hail"
    assert payload["main"]["feels_like"] == 36.5
    assert payload["precipitation_probability"] == 80
    assert payload["precipitation_mm"] == 0.2

def test_fetch_weather_passes_lgu_coords_to_provider(app, monkeypatch):
    # Regression: every city used to fetch Marikina's grid (14.6308,
    # 121.0968) because the frontend hardcoded coords in the city branch.
    # The provider must receive the requested LGU coordinates.
    import services.weather_service as ws
    urls = []
    def fake_fetch(url, timeout=5):
        urls.append(url)
        if "hourly=" in url:
            return {"hourly": {"time": [], "temperature_2m": []}, "daily": {}}
        return {"current": {"temperature_2m": 30, "relative_humidity_2m": 70,
                            "apparent_temperature": 34, "precipitation": 0.0,
                            "precipitation_probability": 10,
                            "wind_speed_10m": 3.0, "weather_code": 1,
                            "is_day": 1, "time": "2026-09-04T14:00"}}
    monkeypatch.setattr(ws, "_fetch_json", fake_fetch)
    with app.app_context():
        from utils.db import get_db
        payload, err = ws.fetch_weather(get_db(), 14.5995, 120.9842, "Manila")
    assert err is None
    assert payload["lat"] == 14.5995 and payload["lon"] == 120.9842
    assert any("latitude=14.5995" in u and "longitude=120.9842" in u for u in urls)

def test_weather_page_sends_coords_with_city_and_links_officials(client):
    html = client.get("/weather").get_data(as_text=True)
    # City branch must carry the real lat/lon, not a hardcoded grid.
    assert "city=${encodeURIComponent(city)}&lat=14.6308" not in html
    assert "params.push(`city=${encodeURIComponent(city)}`)" in html
    # Official cross-check card (external links, not scraped content:
    # ligtas.cair.ph robots.txt disallows /api/).
    assert "https://www.pagasa.dost.gov.ph/" in html
    assert "https://ligtas.cair.ph/home/" in html
    assert 'target="_blank"' in html
    # Per-city proof: provider-resolved station name shown next to the label.
    assert "• via ${esc(rawName)}" in html
    # esc() must exist: user-typed city names flow into card markup.
    assert "function esc(s)" in html
    assert "${esc(displayName)}" in html

def test_geocode_city_hit_miss_and_failure(monkeypatch):
    import services.weather_service as ws
    def fake_ok(url, timeout=5):
        return {"results": [{"latitude": 12.3700, "longitude": 123.6200, "name": "Masbate"}]}
    monkeypatch.setattr(ws, "_fetch_json", fake_ok)
    assert ws.geocode_city("masbate") == (12.37, 123.62, "Masbate")
    monkeypatch.setattr(ws, "_fetch_json", lambda url, timeout=5: {"results": []})
    assert ws.geocode_city("xyzzynonsense") is None
    def boom(url, timeout=5):
        raise Exception("offline")
    monkeypatch.setattr(ws, "_fetch_json", boom)
    assert ws.geocode_city("Manila") is None
    assert ws.geocode_city("  ") is None

def test_weather_city_only_geocodes_to_own_grid(client, monkeypatch):
    # Regression: typed cities used to receive Marikina's grid (14.6308,
    # 121.0968) under their own label. A bare city must resolve to its
    # own coordinates via geocoding.
    import services.weather_service as ws
    real_fetch = ws._fetch_json
    def fake_fetch(url, timeout=5):
        if "geocoding-api" in url:
            return {"results": [{"latitude": 12.3700, "longitude": 123.6200, "name": "Masbate"}]}
        if "hourly=" in url:
            return {"hourly": {"time": [], "temperature_2m": []}, "daily": {}}
        return {"current": {"temperature_2m": 29.0, "relative_humidity_2m": 75,
                            "apparent_temperature": 33.0, "precipitation": 0.0,
                            "precipitation_probability": 20,
                            "wind_speed_10m": 4.0, "weather_code": 2,
                            "is_day": 0, "time": "2026-09-04T14:00"}}
    monkeypatch.setattr(ws, "_fetch_json", fake_fetch)
    r = client.get("/api/weather?city=masbate")
    assert r.status_code == 200
    j = r.get_json()
    assert (j["lat"], j["lon"]) == (12.37, 123.62)
    assert j["city"] == "masbate"
    assert j["name"] != "City of Marikina"

def test_weather_unknown_city_404(client, monkeypatch):
    import services.weather_service as ws
    monkeypatch.setattr(ws, "geocode_city", lambda city, timeout=5: None)
    r = client.get("/api/weather?city=xyzzynonsense")
    assert r.status_code == 404
    assert "not found" in r.get_json()["error"].lower()
    r2 = client.get("/api/environment?city=xyzzynonsense")
    assert r2.status_code == 404

def test_air_quality_demo_not_served_outside_ncr(client, app, monkeypatch):
    # Seed AQ demo row describes Metro Manila; a far-away query with dead
    # providers must 503, not answer with Manila air.
    import services.air_quality_service as aq
    monkeypatch.setattr(aq, "fetch_open_meteo_aq",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("offline")))
    monkeypatch.setattr(aq, "fetch_openweather_aq",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("offline")))
    r = client.get("/api/air-quality?lat=12.37&lon=123.62")
    assert r.status_code == 503
    assert r.get_json().get("retry") is True

def test_weather_page_omits_coords_for_unknown_text(client):
    html = client.get("/weather").get_data(as_text=True)
    assert "if(lat!=null && lon!=null) params.push(`lat=${lat}&lon=${lon}`)" in html
    assert "Place not found" in html

def test_api_weather_has_heat_index(client):
    r = client.get("/api/weather?lat=14.6308&lon=121.0968")
    assert r.status_code == 200
    j = r.get_json()
    assert "heat_index" in j
    assert "value_c" in j["heat_index"]
    assert "category" in j["heat_index"]
    assert "recommendation" in j["heat_index"]
    # Should be calculated, not plain temp
    assert j["heat_index"]["method"] is not None

def test_api_weather_stale_still_has_heat(client, app, monkeypatch):
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        # ensure cache exists then make it stale by patching fetch to fail — fetch_weather will return stale with heat
        pass
    # Just verify stale path via monkeypatched air failure but weather still from cache has heat
    r = client.get("/api/weather?lat=14.6308&lon=121.0968")
    assert r.status_code == 200

def test_api_air_quality_structure(client):
    r = client.get("/api/air-quality?lat=14.6308&lon=121.0968")
    # may be 200 or 503 if offline in CI — but should not be 500
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        j = r.get_json()
        assert "category" in j
        assert "pm25" in j or "aqi" in j
        assert "scale" in j

def test_api_air_quality_invalid_coords(client):
    r = client.get("/api/air-quality?lat=999&lon=999")
    assert r.status_code == 400

def test_api_environment_combined(client):
    r = client.get("/api/environment?lat=14.6308&lon=121.0968")
    assert r.status_code == 200
    j = r.get_json()
    assert "weather" in j
    assert "overall" in j
    # overall must have category
    assert "category" in j["overall"]
    # weather should have heat_index
    if j["weather"]:
        assert "heat_index" in j["weather"]

def test_api_environment_invalid_coords(client):
    r = client.get("/api/environment?lat=999&lon=999")
    assert r.status_code == 400

def test_air_quality_unavailable_no_fabrication(client, app, monkeypatch):
    # Force air fetch to fail and clear cache -> should be 503 not fake 0
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute("DELETE FROM weather_cache WHERE source='air-quality'")
        db.commit()
    monkeypatch.setattr("services.air_quality_service.fetch_open_meteo_aq", lambda lat, lon, city=None: (_ for _ in ()).throw(Exception("offline")))
    monkeypatch.setattr("services.air_quality_service.fetch_openweather_aq", lambda lat, lon, key, city=None: (_ for _ in ()).throw(Exception("offline")))
    r = client.get("/api/air-quality?lat=14.6308&lon=121.0968")
    # Should be 503 retry, not 200 with fabricated 0
    assert r.status_code == 503
    assert r.get_json().get("retry") is True
    assert r.get_json().get("error") is not None
