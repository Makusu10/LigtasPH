# AGENTS.md — LigtasPH

## Stack & Entrypoints
- Flask 3.x + SQLite + Vanilla JS + Leaflet/OSM. Factory `app.py:12` `create_app()`; prod entry `wsgi.py:1` (`gunicorn wsgi:app` per `Procfile:1`). Config via `FLASK_ENV` → `config.py:49` `config_by_name` (`development`/`production`/`testing`).
- No `pyproject.toml`, linter, typecheck, or CI. Verification is `pytest` only. No repo-local OpenCode config.

## Commands (exact)
```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app app init-db  # 8 tables per utils/db.py:5 SCHEMA
.venv/bin/python -m flask --app app seed     # idempotent, runs init_db() internally app.py:54-56
.venv/bin/python -m flask --app app run --debug  # :5000; or .venv/bin/python wsgi.py
.venv/bin/python -m pytest -q                                    # 83 tests
.venv/bin/python -m pytest -q tests/test_sprint1.py::test_api_centers_returns_6  # single test
.venv/bin/python run_gui.py  # demo launcher: re-execs into venv, init-db+seed if missing, opens :5000
```
- Always use `.venv/bin/python -m ...` (system python hits `externally-managed-environment`).
- `cp .env.example .env`; OpenWeather/FIRMS keys optional (fallbacks cover dev), `SECRET_KEY` + `ADMIN_*` required non-default only in production.

## Architecture
- 4 blueprints in `app.py:60-68`: `routes/public.py` (`/`, `/map`, `/centers`, `/centers/<id>`, `/weather`, `/hotlines`), `routes/auth.py` (`/admin/login|logout`), `routes/admin.py` (`/admin/*` guarded by `utils/security.py:4` `login_required` → redirect to login), `routes/api.py` (`/api/centers`, `/api/centers/<id>`, `/api/hotlines`, `/api/weather`, `/api/air-quality`, `/api/environment`, `/api/groups`, `/api/locations`, `/api/groups/<code>/locations`, `/api/earthquakes`, `/api/fires`). API blueprint is CSRF-exempt `app.py:72`.
- Query via `utils.db.get_db()`, not `models/` (placeholder package). All center/hotline reads filter `archived=0` (soft delete).
- Occupancy computed in routes, not DB: `Full>=100 / Nearly Full>=80 / Available if Open else Status Unavailable` (`routes/api.py:39`, `routes/public.py:41`).
- Auth: login POST rate-limited `10/minute` (`routes/auth.py:10`); 5 bad passwords → 15-min lockout (`locked_until`); logout is POST-only.

## External services (never fabricate → `503` + `retry:true`)
- Weather `services/weather_service.py:164` `fetch_weather`: fresh cache `<10min` → OpenWeather (only if key set and not placeholder) → Open-Meteo (no key, `Asia/Manila` + `is_day`) → stale `<1h` → `503`. Invalid lat/lng → `400` (`routes/api.py:97-102`).
- Air quality `services/air_quality_service.py:553` `fetch_air_quality`: fresh cache → Open-Meteo Air primary (`us_aqi,pm2_5`, no key) → OpenWeather Air fallback (reuses key) → stale → `503`. PM2.5 classified by DENR DAO 2020-14, US AQI kept labeled separate; heat via Rothfusz from `temp+humidity`; `overall_status()` = max severity (`utils/environment.py:52,104,117`).
- Hazards `services/hazards_service.py`: quakes via USGS (+ cache, `503` offline); fires via NASA FIRMS clamped to PH bbox — without real `FIRMS_MAP_KEY` returns `503` (`:181-185`); `days` must be 1|2, quake `radius_km` 10–2000 else `400`.
- `ProductionConfig.validate()` (`config.py:34`) fail-loud on default `SECRET_KEY`/`ADMIN_*`; called only when `FLASK_ENV=production` (`app.py:22`).

## DB & Seed
- `utils/db.py:5` SCHEMA: 8 tables with CHECKs on lat/lng, capacity, status enums; file DB uses `foreign_keys=ON` + `journal_mode=WAL`.
- `utils/seed.py:7` `seed_db()`: 7 centers (6 open + 1 archived), 12 hotlines, 1 admin (hashed from `ADMIN_USERNAME/PASSWORD`, defaults `admin/admin123`), `weather_cache` demo + `air-quality` demo. Skips non-empty tables → safe to re-run.
- `instance/` + `*.sqlite` gitignored; delete `instance/ligtas.sqlite` to reset.

## Testing Quirks
- `TestingConfig` (`config.py:43`): `DATABASE=":memory:"` mapped to shared `file:memdb_sprint1` (`utils/db.py:126-136`); `close_db` never closes it. `WTF_CSRF_ENABLED=False`, `RATELIMIT_ENABLED=False`. Fixtures are function-scoped `create_app("testing")+init_db()+seed_db()`.
- Offline tests rely on seeded `weather_cache` (200); cache-cleared + monkeypatched provider failure asserts `503` + `retry:true`, never fabricated `0` (`tests/test_sprint1.py:96`, `tests/test_environment.py:150`).

## Gotchas
- DB locked: `Ctrl+C` then `init-db && seed`. Port busy: `--port 5001`. Headless/WSL: browser won't open — visit `http://127.0.0.1:5000` manually.
- `weather_cache.source` allowlist still contains legacy `'noaa'` (`utils/db.py:85`) but no live code calls `api.weather.gov`; weather fallback is OpenWeather → Open-Meteo only.
