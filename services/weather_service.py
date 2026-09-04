"""
Free-API weather service interface for Sprint 1.
Order: cache (<10min) -> OpenWeather (with key) -> Open-Meteo (no key) -> stale cache (<1h) -> 503
No fake data - returns None on double failure so route can return 503.
"""
import json
import time
import urllib.request
import urllib.error
from flask import current_app

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={key}&units=metric"
# Use Asia/Manila for PH-time background + is_day + high/low
OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,precipitation_probability,wind_speed_10m,weather_code,is_day&timezone=Asia%2FManila"
OPENMETEO_HOURLY_URL = "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,precipitation_probability&daily=temperature_2m_max,temperature_2m_min&forecast_days=1&timezone=Asia%2FManila"

# Complete WMO weather-code table (https://open-meteo.com/en/docs).
# Every code maps to a label so the UI never shows a raw "WMO 96".
WMO_MAP = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

def _fetch_json(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "LigtasPH/1.0 (free-tier)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())

def get_cached(db, lat, lon, city=None, max_age_sec=600):
    try:
        # Exclude air-quality rows — weather cache only
        if city:
            row = db.execute("SELECT * FROM weather_cache WHERE city=? AND source IN ('cached','openweather','open-meteo','noaa') ORDER BY fetched_at DESC LIMIT 1", (city,)).fetchone()
            if row is None:
                row = db.execute("SELECT * FROM weather_cache WHERE city=? ORDER BY fetched_at DESC LIMIT 1", (city,)).fetchone()
                # fallback if only air-quality exists — but filter to weather-like payload
                if row and row["source"] == "air-quality":
                    row = None
        else:
            row = db.execute("SELECT * FROM weather_cache WHERE lat=? AND lng=? AND source IN ('cached','openweather','open-meteo','noaa') ORDER BY fetched_at DESC LIMIT 1", (lat, lon)).fetchone()
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

def fetch_openweather(lat, lon, key, city=None):
    data = _fetch_json(OPENWEATHER_URL.format(lat=lat, lon=lon, key=key))
    # PH time for day/night
    try:
        import datetime as _dt
        ph_hour = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).hour
        is_day = 1 if 6 <= ph_hour < 18 else 0
    except Exception:
        is_day = 1
    temp = data["main"]["temp"]
    return {
        "source": "openweather",
        "name": data.get("name", city or "Unknown"),
        "city": city or data.get("name", ""),
        "lat": lat,
        "lon": lon,
        "is_day": is_day,
        "weather": [{"description": data["weather"][0]["description"], "icon": data["weather"][0].get("icon","01d")}],
        "main": {"temp": temp, "humidity": data["main"]["humidity"], "feels_like": data["main"].get("feels_like"), "temp_max": data["main"].get("temp_max", temp+2), "temp_min": data["main"].get("temp_min", temp-1)},
        "wind": {"speed": data["wind"]["speed"]},
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

def fetch_open_meteo(lat, lon, city=None):
    data = _fetch_json(OPENMETEO_URL.format(lat=lat, lon=lon))
    cur = data.get("current", {})
    code = cur.get("weather_code", 0)
    is_day = cur.get("is_day", 1)
    # Prefer city name when provided, else lat,lon string
    display_name = city if city else f"{lat},{lon}"
    temp = cur.get("temperature_2m")
    # apparent_temperature is the model's true "feels like" (accounts for
    # humidity/wind); fall back to raw temp only if the provider omits it.
    feels = cur.get("apparent_temperature", temp)
    payload = {
        "source": "open-meteo",
        "name": display_name,
        "city": city or "",
        "lat": lat,
        "lon": lon,
        "is_day": int(is_day) if is_day is not None else 1,
        "weather": [{"description": WMO_MAP.get(code, f"WMO {code}"), "icon": "02d", "code": code}],
        "main": {"temp": temp, "humidity": cur.get("relative_humidity_2m"), "feels_like": feels},
        "precipitation_mm": cur.get("precipitation"),
        "precipitation_probability": cur.get("precipitation_probability"),
        "wind": {"speed": cur.get("wind_speed_10m")},
        "fetched_at": cur.get("time", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    }
    # Try to attach hourly + daily high/low for visuals — non-fatal
    try:
        hdata = _fetch_json(OPENMETEO_HOURLY_URL.format(lat=lat, lon=lon))
        hourly = hdata.get("hourly", {})
        times = hourly.get("time", [])[:24]
        temps = hourly.get("temperature_2m", [])[:24]
        humids = hourly.get("relative_humidity_2m", [])[:24]
        winds = hourly.get("wind_speed_10m", [])[:24]
        codes = hourly.get("weather_code", [])[:24]
        pops = (hourly.get("precipitation_probability", []) or [])[:24]
        if times and temps:
            payload["hourly"] = [
                {"time": t, "temp": tp, "humidity": hm, "wind": w, "code": c, "desc": WMO_MAP.get(c, f"WMO {c}"), "pop": (pops[i] if i < len(pops) else None)}
                for i, (t, tp, hm, w, c) in enumerate(zip(times, temps, humids, winds, codes))
            ]
            # High/Low from hourly if daily missing
            try:
                vals = [t for t in temps if t is not None]
                if vals:
                    payload["main"]["temp_max"] = max(vals)
                    payload["main"]["temp_min"] = min(vals)
            except Exception:
                pass
        daily = hdata.get("daily", {})
        if daily.get("temperature_2m_max") and daily.get("temperature_2m_min"):
            payload["main"]["temp_max"] = daily["temperature_2m_max"][0]
            payload["main"]["temp_min"] = daily["temperature_2m_min"][0]
        # Ensure is_day from hourly fetch if missing
        if "is_day" not in payload and hourly:
            pass
    except Exception:
        pass
    # Fallback high/low if still missing
    if payload["main"].get("temp_max") is None and payload["main"].get("temp") is not None:
        payload["main"]["temp_max"] = payload["main"]["temp"] + 2
        payload["main"]["temp_min"] = payload["main"]["temp"] - 1
    return payload

def _attach_heat_index(payload):
    """Attach official Heat Index (not feels-like) using Rothfusz from temp+humidity."""
    try:
        from utils.environment import calculate_heat_index, classify_heat_index
        temp = payload.get("main", {}).get("temp")
        rh = payload.get("main", {}).get("humidity")
        # Prefer provider's explicit heat index if they ever supply it — currently none do
        hi = None
        # Check if provider explicitly supplied heat_index
        if payload.get("main", {}).get("heat_index") is not None:
            hi = payload["main"]["heat_index"]
        else:
            hi = calculate_heat_index(temp, rh)
        if hi is not None:
            info = classify_heat_index(hi)
            payload["heat_index"] = {
                "value_c": hi,
                "category": info["category"],
                "color": info["color"],
                "recommendation": info["recommendation"],
                "severity": info["severity"],
                "colors": info["colors"],
                "method": "Rothfusz (NWS) from temp+humidity" if payload.get("main", {}).get("heat_index") is None else "provider explicit",
            }
    except Exception:
        pass
    return payload

def fetch_weather(db, lat=14.6308, lon=121.0968, city=None):
    # 1. cache
    cached, src = get_cached(db, lat, lon, city)
    if cached:
        cached["_cache_source"] = src
        cached["source"] = src or cached.get("source", "cached")
        # Ensure heat index present even for cached (old) payloads
        _attach_heat_index(cached)
        return cached, None
    # 2. OpenWeather
    key = current_app.config.get("OPENWEATHER_API_KEY", "")
    if key and key != "YOUR_OPENWEATHER_API_KEY":
        try:
            payload = fetch_openweather(lat, lon, key, city)
            _attach_heat_index(payload)
            cache_payload(db, lat, lon, city or payload.get("name"), "openweather", payload)
            return payload, None
        except Exception as e:
            # fall through to open-meteo
            pass
    # 3. Open-Meteo (free, no key)
    try:
        payload = fetch_open_meteo(lat, lon, city)
        _attach_heat_index(payload)
        cache_payload(db, lat, lon, city or payload.get("name") or f"{lat},{lon}", "open-meteo", payload)
        return payload, None
    except Exception as e:
        pass
    # 4. try stale cache
    stale, src = get_cached(db, lat, lon, city, max_age_sec=3600)
    if stale:
        stale["_stale"] = True
        stale["source"] = src or stale.get("source", "cached")
        _attach_heat_index(stale)
        return stale, None
    return None, "Weather unavailable. Please check connection and retry."
