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
# GEMINI_API_KEY optional, Open-Meteo + api.weather.gov need no key (free fallback)
```

### 4. Init DB & seed (sample centers/hotlines/weather_cache + admin hash)
```bash
flask --app app init-db
flask --app app seed
# admin default from .env: admin / admin123 (hashed, not plaintext)
```

### 5. Run dev server
```bash
flask --app app run --debug
# or: python wsgi.py
```
Open `http://127.0.0.1:5000` → `Home | Map | Centers | Weather | Hotlines | Admin Login`

---

## 🛠️ Available Commands
| Command | Description |
| :--- | :--- |
| `flask --app app run` | Flask dev server (auto reload) |
| `flask --app app init-db` | Create 5 tables (FK ON, CHECKs, indexes) |
| `flask --app app seed` | Seed 7 centers (Available/Nearly/Full/archived), 12 hotlines, 1 admin (hashed), weather_cache demo |
| `gunicorn wsgi:app` | Production server (Render/PythonAnywhere) |
| `pytest -q` | Run 15 Sprint 1 tests (auth, API, weather, 404) |
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
- **Frontend**: HTML5, CSS3 (Inter font, tokens #155EEF/#102A43/#D92D20/#F79009/#039855/#F5F7FA), Vanilla JS, Leaflet 1.9 + OSM, Lucide icons
- **Backend**: Flask 3.x, Flask-WTF (CSRF), Flask-Limiter (5/15min lockout), Werkzeug hash, python-dotenv, whitenoise
- **DB**: SQLite (`instance/ligtas.sqlite`, `PRAGMA foreign_keys=ON`), 5 tables: `administrators`, `evacuation_centers`, `center_status_updates`, `emergency_hotlines`, `weather_cache`
- **Weather**: `services/weather_service.py` → `cache<10min → OpenWeather (key) → Open-Meteo (no key) → api.weather.gov (no key, PH returns []) → 503+retry`, never fabricates
- **Structure**: `app.py` (factory) + `wsgi.py`, `config.py`, `routes/{public,auth,admin,api}.py`, `models/`, `services/`, `utils/{db,seed,validators,security}`, `templates/{public,admin,errors,partials}`, `static/{css,js,images}`, `tests/`

---

## 🗺️ Key Features (Sprint 1)
1. **Home** stats (total/available/nearly/full) + map preview + recently updated + last_updated + emergency notice
2. **Evacuation Map** markers colored green/orange/red/gray + text label, search/filter city/status/supply, `fitBounds`, Use My Location, list view, popup with occupancy/supply/directions
3. **Directory** searchable cards with progress bar + badges + sort (name/available/occupancy/recent) + empty state
4. **Center Detail** computed `available_slots`, `occupancy_pct`, `occupancy_status` (Available<80/Nearly 80-99/Full), 5 supplies, notes, `tel:` + directions
5. **Weather** proxy hides key, OpenWeather → Open-Meteo fallback, handles 400/503 + retry
6. **Hotlines** filter city/category/q, `tel:` + Copy, empty per locality
7. **Admin** hashed login, session, protected `/admin/*`, dashboard (total capacity/occupancy/low-supply/stale>7d), centers/hotlines tables

---

## 🔒 Security
- Werkzeug `generate_password_hash`/`check_password_hash`, Flask session `HttpOnly/SameSite`, CSRF, parameterized queries, escaped templates, `SECRET_KEY` via env, 5-attempt lockout, no secrets committed.

## ♿ Accessibility & Responsive
- Inter 16px, semantic HTML, ARIA, keyboard, focus ring, contrast, color+label+icon, 44px taps, media `768px` collapse, 320/375/768/1024/1440 tested.

## 🧪 Testing
```bash
pytest -q  # 15 passed: home/map/directory/weather/hotlines/admin pages, protected redirect, api centers/hotlines/weather (200+400), detail 200/404, login 401/302+dashboard
```

## Known MVP Limitations
- Offline: requires network for tiles/weather live; cached demo works offline after first seed
- Unofficial sites & nationwide hotline coverage not in MVP
- NOAA `api.weather.gov` US-centric → PH returns empty (handled gracefully)
- No file uploads; archived flag instead of hard delete

## Environment Variables
See `.env.example`: `SECRET_KEY`, `FLASK_ENV`, `DATABASE_URL`, `ADMIN_USERNAME/PASSWORD`, `OPENWEATHER_API_KEY`, `GEMINI_API_KEY` (optional), Open-Meteo & NOAA no key.

## License
Demo for academic use. Sample data flagged "Development — not verified live."
