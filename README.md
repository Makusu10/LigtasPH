# LigtasPH: Integrated Calamity Response and Evacuation Mapping System

**LigtasPH** is a centralized disaster-information platform for residents of the Philippines. It locates official evacuation centers, tracks occupancy and supply status, shows current weather, and provides emergency hotlines per city/municipality. Admin portal for LGU/DRRMO to maintain centers, occupancy, supplies, and hotlines.

> Sprint 1 MVP: Flask + SQLite + Vanilla JS + Leaflet/OSM + Inter + Lucide. Full Express → Flask cutover done. Development sample data flagged as "not verified live."

---

## 🚀 Quick Start (Local)

### Prerequisites
- **Python 3.11+** (tested 3.11.9, also works 3.14)
- **pip** + **venv**
- **Git**

### 1. Clone & venv
```bash
git clone https://github.com/<your-username>/LigtasPH.git
cd LigtasPH
python3 -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure env
```bash
cp .env.example .env
# edit .env: set SECRET_KEY (long random), OPENWEATHER_API_KEY (free 1000/day), ADMIN_USERNAME/PASSWORD
# GEMINI_API_KEY optional, Open-Meteo (weather+air) needs no key; OpenWeather Air Pollution reuses same key
```

### 4. Init DB & seed (sample centers/hotlines/weather_cache + admin hash)
```bash
flask --app app init-db
flask --app app seed
# admin default from .env: admin / admin123 (hashed, not plaintext)
```

### 5. Run / Activate the Website

**Option A — One-click GUI (recommended for demo/lab):**
```bash
python run_gui.py
# Auto-creates venv if missing, installs deps, init-db + seed if needed,
# then opens http://127.0.0.1:5000 in your default browser.
# Works from ANY Python: run_gui.py auto-detects .venv → venv → /tmp/ligtas_venv → env
# and re-executes with that venv's python. Or double-click run_gui.py in Explorer/Finder.
# Ctrl+C in terminal to stop.
```

**Option B — Manual Flask dev server:**
```bash
# Linux / macOS — activate venv first
source venv/bin/activate          # or source .venv/bin/activate

# Windows CMD
venv\Scripts\activate

# Windows PowerShell
venv\Scripts\Activate.ps1

# Then run
flask --app app run --debug       # http://127.0.0.1:5000 with auto-reload
# or
python wsgi.py                    # same, uses wsgi.py:87
```

**Option C — Production (local prod check):**
```bash
gunicorn wsgi:app                 # http://127.0.0.1:8000 (Render uses this; Procfile: web: gunicorn wsgi:app)
```

**How to know it worked:**
- Browser shows `LIGTASPH` nav: `Home | Evacuation Map | Evacuation Centers | Weather | Emergency Hotlines | Admin Login`
- Home shows stats `total 7` (6 live +1 archived hidden) + map preview + recently updated.
- Login to admin: `http://127.0.0.1:5000/admin/login` → `admin` / `admin123` → redirects to `/admin/dashboard` (protected route returns 302 when anon).

**Deactivate venv when done:**
```bash
deactivate
```

**Troubleshooting:**
- `externally-managed-environment` → use `python3 -m venv venv` then `source venv/bin/activate` first.
- `ModuleNotFoundError: No module named 'flask'` → `pip install -r requirements.txt` inside venv.
- `port 5000 busy` → `flask --app app run --port 5001` or change `PORT` in `run_gui.py:16`.
- `instance/ligtas.sqlite` locked → stop Flask (`Ctrl+C`) then `flask --app app init-db && flask --app app seed`.
- Browser didn't open (headless/WSL) → manually visit `http://127.0.0.1:5000`.

---

## 🛠️ Available Commands
| Command | Description |
| :--- | :--- |
| `flask --app app run` | Flask dev server (auto reload) |
| `flask --app app init-db` | Create 5 tables (FK ON, CHECKs, indexes) |
| `flask --app app seed` | Seed 7 centers (Available/Nearly/Full/archived), 12 hotlines, 1 admin (hashed), weather_cache demo (incl. heat/AQI demo) |
| `gunicorn wsgi:app` | Production server (Render/PythonAnywhere) |
| `pytest -q` | Run 17+ Sprint 1+2 tests (auth, API, weather, env heat/AQI 503, 404) |
| `pip install -r requirements.txt` | Install Flask, Flask-WTF, Flask-Limiter, gunicorn, whitenoise, pytest |

---

## 📦 Production Deployment

### Render (free)
- Build: `pip install -r requirements.txt`
- Start: `gunicorn wsgi:app`
- Env vars in Dashboard: `SECRET_KEY`, `OPENWEATHER_API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `FLASK_ENV=production`
- Disk: mount `instance/` for SQLite persistence or re-seed on boot

### PythonAnywhere (free)
- Upload, `mkvirtualenv --python=python3.11 ligtas && pip install -r requirements.txt`
- WSGI file: `from app import create_app; application = create_app()`
- Workdir `/home/<user>/LigtasPH`, run `flask --app app init-db && flask --app app seed` in console, set env in Web tab, Reload

---

## 🏗️ Tech Stack & Architecture
- **Frontend**: HTML5, CSS3 (Material 3 liquid-glass matte, Inter/Roboto, tokens --primary/#3b6ef5), Vanilla JS, Leaflet 1.9 + OSM, Lucide + Material Symbols, Visual weather Now + hourly + environmental (Heat/AQI) cards
- **Backend**: Flask 3.x, Flask-WTF (CSRF), Flask-Limiter (5/15min lockout), Werkzeug hash, python-dotenv, whitenoise
- **DB**: SQLite (`instance/ligtas.sqlite`, `PRAGMA foreign_keys=ON`), 5 tables: `administrators`, `evacuation_centers`, `center_status_updates`, `emergency_hotlines`, `weather_cache` (also caches `air-quality` 10m/1h)
- **Weather**: `services/weather_service.py` → `cache<10min → OpenWeather (key, PH is_day) → Open-Meteo (no key, Asia/Manila + is_day + daily High/Low) → stale 1h →503`, never fabricates; Heat Index via Rothfusz (`utils/environment.py`)
- **Air Quality**: `services/air_quality_service.py` → `cache10m → OpenWeather Air Pollution (if key) → Open-Meteo Air Quality (no key, PM2.5/US AQI) → stale 1h →503`; DENR DAO 2020-14 PM2.5 + US EPA AQI labeled separately
- **Structure**: `app.py` (factory) + `wsgi.py`, `config.py`, `routes/{public,auth,admin,api}.py`, `models/`, `services/{weather_service,air_quality_service}`, `utils/{db,seed,validators,security,environment}`, `templates/{public,admin,errors,partials}`, `static/{css,js,images}`, `tests/`

---

## 🗺️ Key Features (Sprint 1)
1. **Home** stats (total/available/nearly/full) + map preview + recently updated + last_updated + emergency notice
2. **Evacuation Map** markers colored green/orange/red/gray + text label, search/filter city/status/supply, `fitBounds`, Use My Location, list view, popup with occupancy/supply/directions
3. **Directory** searchable cards with progress bar + badges + sort (name/available/occupancy/recent) + empty state
4. **Center Detail** computed `available_slots`, `occupancy_pct`, `occupancy_status` (Available<80/Nearly 80-99/Full), 5 supplies, notes, `tel:` + directions
5. **Weather** proxy hides key, OpenWeather → Open-Meteo (Asia/Manila, is_day, High/Low) fallback, handles 400/503 + retry; visuals: Now dark/light (PH time), gauges, hourly strip, Heat Index (PAGASA)
6. **Environmental Safety** side-by-side Heat Index + AQI cards with overall status (max severity), PM2.5 µg/m³ (DENR) & US AQI labeled, tinted backgrounds, accessible badges/bars, skeletons
7. **Hotlines** filter city/category/q, `tel:` + Copy, empty per locality
8. **Admin** hashed login, session, protected `/admin/*`, dashboard (total capacity/occupancy/low-supply/stale>7d), centers/hotlines tables

---

## 🔒 Security
- Werkzeug `generate_password_hash`/`check_password_hash`, Flask session `HttpOnly/SameSite`, CSRF, parameterized queries, escaped templates, `SECRET_KEY` via env, 5-attempt lockout, no secrets committed.

## ♿ Accessibility & Responsive
- Inter 16px, semantic HTML, ARIA, keyboard, focus ring, contrast, color+label+icon, 44px taps, media `768px` collapse, 320/375/768/1024/1440 tested.

## 🧪 Testing
```bash
pytest -q  # 17+ passed: home/map/directory/weather/hotlines/admin pages, protected redirect, api centers/hotlines/weather+env (200+400/503), detail 200/404, login 401/302+dashboard + lockout 403, plus utils/environment boundaries (heat 8 values, PM2.5 10 values, overall, unavailable, stale)
```

## Known MVP Limitations
- Offline: requires network for tiles/weather live; cached demo works offline after first seed
- Unofficial sites & nationwide hotline coverage not in MVP
- NOAA `api.weather.gov` US-centric → PH returns empty (handled gracefully)
- No file uploads; archived flag instead of hard delete

## Environment Variables
See `.env.example`: `SECRET_KEY`, `FLASK_ENV`, `DATABASE_URL`, `ADMIN_USERNAME/PASSWORD`, `OPENWEATHER_API_KEY`, `GEMINI_API_KEY` (optional), Open-Meteo weather & air-quality need no key (air fallback reuses `OPENWEATHER_API_KEY` for `/air_pollution`).

## Environmental Indicators

**Heat Index** `utils/environment.py:29` — NWS Rothfusz regression `F` → `C` from `temp`+`humidity` (provider never supplies explicit heat index; OpenWeather `feels_like` is not labeled as Heat Index). PAGASA categories `<27 Not Hazardous | 27-32 Caution | 33-41 Extreme Caution | 42-51 Danger | ≥52 Extreme Danger` with green/yellow/orange/red-orange/dark-red badges + tinted card + bar (gradual, WCAG contrast, not whole-page red).

**Air Quality** `services/air_quality_service.py:12` — Primary `https://air-quality-api.open-meteo.com/v1/air-quality` (no key, PH) `pm2_5, us_aqi` + fallback `https://api.openweathermap.org/data/2.5/air_pollution` (reuses key). DENR DAO 2020-14 PM2.5 `0-25 Good |25.1-35 Fair |35.1-45 Sensitive |45.1-55 Very Unhealthy |55.1-90 Acutely | >91 Emergency` (µg/m³) plus US EPA AQI numeric labeled `US EPA` — never confused. Overall = max severity of heat vs air.

**Cache** `weather_cache` 10m live /1h stale `utils/db.py:80` shared `source` `air-quality`; never fabricates — shows Unavailable + retry. PH timezone `Asia/Manila`, `is_day` for Now card day/night.

Limitations: heat index needs `temp`+`humidity` (unavailable → Unavailable badge); AQI offline/rate-limit → Unavailable (not 0); some rural coords have sparse AQI; feels_like ≠ heat index.

## License
Demo for academic use. Sample data flagged "Development — not verified live."
