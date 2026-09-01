# LigtasPH: Integrated Calamity Response and Evacuation Mapping System

**LigtasPH** is a centralized disaster-information platform for residents of the Philippines. It locates official evacuation centers, tracks occupancy and supply status, shows current weather, and provides emergency hotlines per city/municipality. Admin portal for LGU/DRRMO to maintain centers, occupancy, supplies, and hotlines.

> Sprint 1 MVP: Flask + SQLite + Vanilla JS + Leaflet/OSM + Inter + Lucide. Full Express → Flask cutover done. Development sample data flagged as "not verified live."

---

## 🚀 Quick Start (Local) — How to Run / Activate the Website

### Prerequisites
- **Python 3.11+** (tested 3.11.9, also works 3.14)
- **pip** + **venv** (`python3 -m venv`)
- **Git**

### Recommended: One-Click GUI (easiest for group & demo)

This uses `run_gui.py` which auto-detects/creates your venv, auto-installs deps, auto-seeds DB, and opens the browser.

```bash
# 1. Clone
git clone https://github.com/<your-username>/LigtasPH.git
cd LigtasPH

# 2. (first time only) copy env — edit SECRET_KEY + OPENWEATHER_API_KEY if you have one
cp .env.example .env
# Windows: copy .env.example .env
# GEMINI_API_KEY optional; Open-Meteo + api.weather.gov need NO key (free fallback)

# 3. Double-click or run:
python run_gui.py
# — it auto-finds .venv / venv / /tmp/ligtas_venv / env
# — if no venv exists, it creates ./venv and installs requirements.txt automatically
# — if instance/ligtas.sqlite missing, it runs init-db + seed (7 centers, 12 hotlines, admin admin/admin123 hashed)
# — opens http://127.0.0.1:5000 in your default browser

# Alternative if you already have a venv active:
source .venv/bin/activate   # or venv/bin/activate; Windows: .venv\Scripts\activate
python run_gui.py
```

> **Stop:** `Ctrl+C` in terminal. **Stuck?** See troubleshooting below.

### Manual (step-by-step — for control / lab defense)

```bash
# 1. Clone & venv
git clone https://github.com/<your-username>/LigtasPH.git
cd LigtasPH
python3 -m venv .venv            # creates .venv (also matches venv/ or env/)
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt  # Flask 3.x, Flask-WTF, Flask-Limiter, gunicorn, whitenoise, pytest, python-dotenv

# 3. Configure env
cp .env.example .env
# edit .env with a text editor:
# SECRET_KEY=change-me-to-a-long-random-string
# OPENWEATHER_API_KEY=your_free_key (1000/day)  # optional for demo; Open-Meteo works without key
# ADMIN_USERNAME=admin
# ADMIN_PASSWORD=admin123
# GEMINI_API_KEY=... (optional)

# 4. Init DB & seed (sample centers/hotlines/weather_cache + admin hash)
flask --app app init-db
flask --app app seed
# → instance/ligtas.sqlite 76K created
# → admin hashed (scrypt), not plaintext; try: admin / admin123

# 5. Run dev server (pick one)
flask --app app run --debug      # auto-reload, debug on
# or
python wsgi.py                   # same as flask run, used for gunicorn/production parity
# or (production preview)
gunicorn wsgi:app --bind 127.0.0.1:5000

# 6. Open browser
# → http://127.0.0.1:5000  (nav: Home | Evacuation Map | Evacuation Centers | Weather | Emergency Hotlines | Admin Login)
# → Admin Login: admin / admin123  → redirects to /admin/dashboard (protected, 302 if anon)
```

### Activate Again Next Time

```bash
# If using venv:
source .venv/bin/activate        # or venv/bin/activate
flask --app app run --debug      # or python run_gui.py (auto-detects venv, no need to activate manually)

# If you closed and lost venv activation, run_gui.py still works from system python:
python run_gui.py                # it will hop into .venv automatically (see run_gui.py:22-26 candidates .venv→venv→/tmp/ligtas_venv→env)
```

### Deactivate / Switch

```bash
deactivate                       # leaves venv
# to remove venv completely (fresh start):
# Windows: rmdir /s /q venv
# macOS/Linux: rm -rf .venv venv
```

### Troubleshooting — Website Won’t Activate

| Symptom | Fix |
| :--- | :--- |
| `externally-managed-environment` on `pip install` | Use venv: `python3 -m venv .venv && source .venv/bin/activate` then `pip install -r requirements.txt` — never use `--break-system-packages` |
| `no such table: evacuation_centers` / blank home | DB not seeded: `flask --app app init-db && flask --app app seed` |
| `ModuleNotFoundError: flask` | venv not active or deps not installed: `source .venv/bin/activate && pip install -r requirements.txt` or just `python run_gui.py` (auto-installs) |
| `Address already in use :5000` | Another server running: `flask --app app run --port 5001` or `lsof -i :5000 && kill <pid>` |
| `BuildError: Could not build url for endpoint 'home'` | You’re on old Express code — `git pull` and ensure `app.py` uses blueprints (`routes/public.py:public.home`) |
| `pytest` fails `401/302` | DB was wiped — re-seed with correct `ADMIN_PASSWORD` from `.env`, then `pytest -q` expects `admin/admin123` if `.env` not set |
| Browser doesn’t open | Manual: open `http://127.0.0.1:5000` yourself; check terminal for `* Running on http://127.0.0.1:5000` |

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
