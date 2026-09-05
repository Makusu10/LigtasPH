# AGENTS.md — LigtasPH

## Stack & Entrypoints
- Flask 3.x + SQLite + Vanilla JS + Leaflet/OSM. Factory `app.py:12` `create_app()`; prod entry `wsgi.py:1` (`gunicorn wsgi:app` per `Procfile:1`). Config via `FLASK_ENV` → `config.py:50` `config_by_name` (`development`/`production`/`testing`).
- No `pyproject.toml`, linter, typecheck, or CI. Verification is `pytest` only. No repo-local OpenCode config.

## Commands (exact)
```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app app init-db  # 10 tables per utils/db.py:5 SCHEMA
.venv/bin/python -m flask --app app seed     # idempotent, runs init_db() internally app.py:69-73
.venv/bin/python -m flask --app app import-geojson [path]  # Sprint 2: load data/ncr_evacuation_centers.geojson (idempotent, default path)
.venv/bin/python -m flask --app app run --debug  # :5000; or .venv/bin/python wsgi.py
.venv/bin/python -m pytest -q                                    # 137 tests
.venv/bin/python -m pytest -q tests/test_sprint1.py::test_api_centers_cover_all_ncr_lgus  # single test
.venv/bin/python run_gui.py  # demo launcher: re-execs into venv, init-db+seed if missing, opens :5000
```
- Always use `.venv/bin/python -m ...` (system python hits `externally-managed-environment`).
- `cp .env.example .env`; OpenWeather/FIRMS keys optional (fallbacks cover dev), `SECRET_KEY` + `ADMIN_*` required non-default only in production.

## Architecture
- 4 blueprints in `app.py:76-84`: `routes/public.py` (`/`, `/map`, `/centers`, `/centers/<id>`, `/weather`, `/hotlines`), `routes/auth.py` (`/admin/login|logout`), `routes/admin.py` (`/admin/*` guarded by `utils/security.py:4` `login_required` → redirect to login), `routes/api.py` (`/api/centers`, `/api/centers/version`, `/api/centers/<id>`, `/api/hotlines`, `/api/ncr-lgus` static 17 LGUs, `/api/weather`, `/api/air-quality`, `/api/environment`, `/api/groups`, `/api/locations`, `/api/groups/<code>/locations`, `/api/announcements`, `/api/earthquakes`, `/api/fires`). API blueprint is CSRF-exempt `app.py:88`.
- `create_app()` self-heals file DBs via `init_db()` on startup (`app.py:54-59`; skipped for `:memory:`) — new tables appear without wiping data. `run_gui.py:93-113` does the same + `seed_db()`; binds `0.0.0.0:5000` with `use_reloader=False` so the browser opens once.
- Query via `utils.db.get_db()`, not `models/` (placeholder package). All center/hotline reads filter `archived=0` (soft delete).
- Occupancy computed in routes, not DB: `Full>=100 / Nearly Full>=80 / Available if Open else Status Unavailable` (`routes/api.py:40`, `routes/public.py:41`). NULL capacity (Sprint 2 imports until an admin sets numbers) → `Status Unavailable` with null pct/slots, never counted as Available (`_occupancy_status()` in `routes/api.py`). Note: home-page counters (`routes/public.py`) now exclude NULL-capacity centers into a separate `unknown` stat (matches API/detail); hero links deep-link via `/map?city=` + `/centers?city=` hydration.
- Auth: login POST rate-limited `10/minute` (`routes/auth.py:10`); 5 bad passwords → 15-min lockout (`locked_until`); logout is POST-only.
- Announcements (`announcements` table): `scope=all|city|radius`, `severity=info|warning|critical`; `/api/announcements` always returns `all`, filters `city`/`radius` rows only when matching params supplied (`routes/api.py:345`).
- Maps: `MAPBOX_TOKEN` (public `pk.*` only) → Mapbox 2D/3D, empty → OSM fallback. `NOAH/` raw sources (~250 MB) are gitignored; only `static/noah/*.geojson` from `scripts/convert_noah.py` is committed.

## External services (never fabricate → `503` + `retry:true`)
- Weather `services/weather_service.py:206` `fetch_weather`: fresh cache `<10min` → OpenWeather (only if key set and not placeholder) → Open-Meteo (no key, `Asia/Manila` + `is_day`) → stale `<1h` → `503`. Invalid lat/lng → `400`, unknown `city` (geocode miss) → `404` — no silent default-grid substitution (`routes/api.py:130-158`).
- Air quality `services/air_quality_service.py:571` `fetch_air_quality`: fresh cache → Open-Meteo Air primary (`us_aqi,pm2_5`, no key) → OpenWeather Air fallback (reuses key) → stale → `503`. PM2.5 classified by DENR DAO 2020-14, US AQI kept labeled separate; heat via Rothfusz from `temp+humidity`; `overall_status()` = max severity (`utils/environment.py`). AQ demo seed row is NCR-box-guarded — queries outside NCR never serve it (`:292-296`).
- Hazards `services/hazards_service.py`: quakes via USGS feed (5-min fresh / 1-h stale, PH-bbox default, `503` offline); fires via NASA FIRMS clamped to PH bbox — without real `FIRMS_MAP_KEY` returns `503` (`:181-185`); `days` must be 1|2, quake `radius_km` 10–2000 else `400`.
- `ProductionConfig.validate()` (`config.py:35`) fail-loud on default `SECRET_KEY`/`ADMIN_*`; called only when `FLASK_ENV=production` (`app.py:22`).

## DB & Seed
- `utils/db.py:5` SCHEMA: 10 tables with CHECKs on lat/lng, capacity, status enums; file DB uses `foreign_keys=ON` + `journal_mode=WAL`. `evacuation_centers.capacity/current_occupancy` are nullable (Sprint 2 imports); `source/verified/needs_review/review_reason` track import provenance; `staging_centers` quarantines ungeocodable rows. `_migrate_centers()` rebuilds pre-Sprint-2 tables in place (ADD COLUMN can't drop NOT NULL). `weather_cache.source` allowlist still contains legacy `'noaa'` (`utils/db.py:85`) but no live code calls `api.weather.gov`; weather fallback is OpenWeather → Open-Meteo only.
- `utils/seed.py:7` `seed_db()`: 21 centers (20 open across all 17 NCR LGUs + 1 archived), ~29 hotlines, 1 admin (hashed from `ADMIN_USERNAME/PASSWORD`, defaults `admin/admin123`), `weather_cache` demo + `air-quality` demo. Centers/weather seed only when tables empty, but hotlines are insert-missing on `(agency, contact_number)` — re-seed picks up new hotlines without duplicating.
- Sprint 2 import (`scripts/import_evac_centers.py`, pure functions + stats dict): `data/ncr_evacuation_centers.geojson` (868 features → 836 live + 32 staged). City names normalized via `CITY_MAP` (unknown → quarantine, never guessed); addresses synthesized `<name>, <barangay>, <city>` with deterministic suffixes (`plan_addresses()` — re-imports UPDATE, never duplicate); re-import refreshes geocoded fields only, never clobbers admin-set capacity/occupancy/contacts. GeoJSON coords are `[lon, lat]` — the importer asserts ranges.
- `instance/` + `*.sqlite` gitignored; delete `instance/ligtas.sqlite` to reset.

## Testing Quirks
- `TestingConfig` (`config.py:44`): `DATABASE=":memory:"` mapped to shared `file:memdb_sprint1` (`utils/db.py:146-156`); `close_db` never closes it. `WTF_CSRF_ENABLED=False`, `RATELIMIT_ENABLED=False`. Testing also blanks `OPENWEATHER_API_KEY` (`app.py:29-32`) so provider-failure tests see real `503`s. Fixtures are function-scoped `create_app("testing")+init_db()+seed_db()`.
- Shared-DB pollution: rows inserted by one test file persist for later files in the same process (seed skips non-empty tables). Consequences: `test_sprint1` locks the admin account (later login-needing tests must reset `failed_attempts/locked_until`) and inserts a `Closed Test` center; center-inserting tests must use unique names and delta/exclusion assertions, never absolute counts.
- Offline tests rely on seeded `weather_cache` (200); cache-cleared + monkeypatched provider failure asserts `503` + `retry:true`, never fabricated `0` (`tests/test_sprint1.py:106`, `tests/test_environment.py`).
- Live-count assertions: `/api/centers` returns 20 (archived excluded), `/api/centers/version` count is 20 (`tests/test_sprint1.py:40`, `tests/test_centers_live.py:30`).

## Gotchas
- DB locked: `Ctrl+C` then `init-db && seed`. Port busy: `--port 5001`. Headless/WSL: browser won't open — visit `http://127.0.0.1:5000` manually.
