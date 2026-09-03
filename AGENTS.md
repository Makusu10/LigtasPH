# AGENTS.md — LigtasPH

## Stack & Entrypoints
- Flask 3.x + SQLite + Vanilla JS + Leaflet/OSM. Factory `app.py:12` `create_app()`, prod entry `wsgi.py:1` (`app` for gunicorn). Config via `FLASK_ENV` → `config.py:48` `config_by_name` (`development`/`production`/`testing`).
- No `pyproject.toml`, linter, typecheck, or CI. Only `requirements.txt` + `pytest` for verification. No repo-local `.opencode/skills/`.

## Commands (exact)
```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app app init-db  # 5 tables per utils/db.py:5 SCHEMA
.venv/bin/python -m flask --app app seed     # idempotent, runs init_db() internally app.py:54-56
.venv/bin/python -m flask --app app run --debug  # :5000; or .venv/bin/python wsgi.py
.venv/bin/python -m gunicorn wsgi:app         # prod — Procfile:1
.venv/bin/python run_gui.py                   # demo launcher: re-execs into venv, init-db+seed if missing, opens :5000
.venv/bin/python -m pytest -q                                    # 66 passed
.venv/bin/python -m pytest -q tests/test_sprint1.py::test_api_centers_returns_6  # single test
```
- Use `.venv/bin/python -m ...` (bare `.venv/bin/pytest` breaks imports; system python hits `externally-managed-environment`).

## Architecture
- 4 blueprints in `app.py:60-68`: `routes/public.py` (`/`, `/map`, `/centers`, `/centers/<id>`, `/weather`, `/hotlines`), `routes/auth.py` (`/admin/login|logout`), `routes/admin.py` (`/admin/*` + `utils/security.py:4` `login_required`), `routes/api.py` (`/api/centers`, `/api/centers/<id>`, `/api/hotlines`, `/api/weather`, `/api/air-quality`, `/api/environment`). API blueprint is CSRF-exempt `app.py:72`.
- Occupancy computed in routes, not DB: `Full>=100 / Nearly Full>=80 / Available if Open else Status Unavailable` (`routes/api.py:29`, `routes/public.py:41`).
- Weather `services/weather_service.py:164` `fetch_weather`: cache `<10min` → OpenWeather (if key set, not placeholder) → Open-Meteo (no key, `Asia/Manila` + `is_day`) → stale `<1h` → `503` with `retry:true`. Never fabricates; lat/lng validated `routes/api.py:88-92`.
- Air quality `services/air_quality_service.py:553`: cache `10m` → Open-Meteo Air (`us_aqi,pm2_5`, no key) → OpenWeather Air (reuses key) → stale `1h` → `503`. PM2.5 classified by DENR DAO 2020-14, US AQI kept labeled separate (`utils/environment.py:28,104`). Heat via Rothfusz from `temp+humidity` (`utils/environment.py:52`); `overall_status()` = max severity.
- `ProductionConfig.validate()` (`config.py:33`) fail-loud on default `SECRET_KEY`/`ADMIN_*`; called only when `FLASK_ENV=production` (`app.py:22`).

## DB & Seed
- `utils/db.py:5` SCHEMA: 5 tables with CHECKs on lat/lng, capacity, status enums. `archived` = soft delete (all API/public queries filter `archived=0`).
- `utils/seed.py:7` `seed_db()`: 7 centers (6 open + 1 archived), 12 hotlines, 1 admin (hashed from `ADMIN_USERNAME/PASSWORD`, defaults `admin/admin123`), `weather_cache` demo + `air-quality` demo. Skips non-empty tables → safe to re-run.
- `instance/` + `*.sqlite` gitignored; file DB uses `foreign_keys=ON` + `journal_mode=WAL`. Testing `:memory:` maps to shared `file:memdb_sprint1` (`utils/db.py:98-107`); `close_db` never closes it. Delete `instance/ligtas.sqlite` to reset.

## Testing Quirks
- `TestingConfig` (`config.py:42`): `DATABASE=":memory:"`, `WTF_CSRF_ENABLED=False`, `RATELIMIT_ENABLED=False`. Fixtures in `tests/test_sprint1.py:6` / `tests/test_environment.py:8` are function-scoped `create_app("testing")+init_db()+seed_db()`.
- Offline tests rely on seeded `weather_cache` (200); cache-cleared + monkeypatched provider failure asserts `503` + `retry:true`, never fabricated `0` (`test_sprint1.py:89`, `test_environment.py:143`).

## Gotchas
- `.env.example` only has `GEMINI/APP_URL/OPENWEATHER` — missing `SECRET_KEY`, `DATABASE_URL`, `ADMIN_USERNAME/PASSWORD` that `README`/`config.py`/`app.py:24` expect. Create `.env` manually.
- Port busy: `--port 5001`. DB locked: `Ctrl+C` then `init-db && seed`. Headless/WSL: browser won't open — visit `http://127.0.0.1:5000` manually.
- `models/__init__.py` is a placeholder — query via `utils.db.get_db()`, not models.
- `api.weather.gov` is US-only — PH returns empty, handled as `503` (see `README` limitations).
