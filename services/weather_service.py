"""
Free-API weather service interface for Sprint 1.
Order: cache (<10min) -> OpenWeather (with key) -> Open-Meteo (no key) -> api.weather.gov (no key, optional)
No fake data - returns None on double failure so route can return 503.
"""
import json
import time
import urllib.request
import urllib.error
from flask import current_app

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}&units=metric"
OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
WEATHER_GOV_ALERTS = "https://api.weather.gov/alerts?point={lat},{lon}"

WMO_MAP = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 61: "Slight rain",
    63: "Moderate rain", 65: "Heavy rain", 80: "Slight showers", 95: "Thunderstorm"
}

def _fetch_json(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "LigtasPH/1.0 (free-tier)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())

def get_cached(db, lat, lon, city=None, max_age_sec=600):
    try:
        if city:
            row = db.execute("SELECT * FROM weather_cache WHERE city=? ORDER BY fetched_at DESC LIMIT 1", (city,)).fetchone()
        else:
            row = db.execute("SELECT * FROM weather_cache WHERE lat=? AND lng=? ORDER BY fetched_at DESC LIMIT 1", (lat, lon)).fetchone()
        if row:
            # check age
            age = db.execute("SELECT (julianday('now') - julianday(fetched_at))*86400 FROM weather_cache WHERE id=?", (row["id"],)).fetchone()[0]
            if age is not None and age < max_age_sec:
                return json.loads(row["payload"]), row["source"]
        return None, None
    except Exception:
        return None, None

def cache_payload(db, lat, lon, city, source, payload):
    try:
        db.execute("INSERT INTO weather_cache (city, lat, lng, source, payload) VALUES (?,?,?,?,?)",
                   (city, lat, lon, source, json.dumps(payload)))
        db.commit()
    except Exception:
        pass

def fetch_openweather(lat, lon, key):
    data = _fetch_json(OPENWEATHER_URL.format(lat=lat, lon=lon, key=key))
    # normalize to common shape
    return {
        "source": "openweather",
        "name": data.get("name", "Unknown"),
        "weather": [{"description": data["weather"][0]["description"], "icon": data["weather"][0].get("icon","01d")}],
        "main": {"temp": data["main"]["temp"], "humidity": data["main"]["humidity"], "feels_like": data["main"].get("feels_like")},
        "wind": {"speed": data["wind"]["speed"]},
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

def fetch_open_meteo(lat, lon):
    data = _fetch_json(OPENMETEO_URL.format(lat=lat, lon=lon))
    cur = data.get("current", {})
    code = cur.get("weather_code", 0)
    return {
        "source": "open-meteo",
        "name": f"{lat},{lon}",
        "weather": [{"description": WMO_MAP.get(code, f"WMO {code}"), "icon": "02d"}],
        "main": {"temp": cur.get("temperature_2m"), "humidity": cur.get("relative_humidity_2m"), "feels_like": cur.get("temperature_2m")},
        "wind": {"speed": cur.get("wind_speed_10m")},
        "fetched_at": cur.get("time", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    }

def fetch_weather(db, lat=14.6308, lon=121.0968, city=None):
    # 1. cache
    cached, src = get_cached(db, lat, lon, city)
    if cached:
        cached["_cache_source"] = src
        cached["source"] = src or cached.get("source", "cached")
        return cached, None
    # 2. OpenWeather
    key = current_app.config.get("OPENWEATHER_API_KEY", "")
    if key and key != "YOUR_OPENWEATHER_API_KEY":
        try:
            payload = fetch_openweather(lat, lon, key)
            cache_payload(db, lat, lon, city or payload.get("name"), "openweather", payload)
            return payload, None
        except Exception as e:
            # fall through to open-meteo
            pass
    # 3. Open-Meteo (free, no key)
    try:
        payload = fetch_open_meteo(lat, lon)
        cache_payload(db, lat, lon, city or payload.get("name"), "open-meteo", payload)
        return payload, None
    except Exception as e:
        pass
    # 4. try stale cache
    stale, src = get_cached(db, lat, lon, city, max_age_sec=3600)
    if stale:
        stale["_stale"] = True
        stale["source"] = src or stale.get("source", "cached")
        return stale, None
    return None, "Weather unavailable. Please check connection and retry."
