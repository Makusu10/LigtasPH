# AGENTS.md — LigtasPH

## Stack & Entrypoints
- Flask 3.x + SQLite + Vanilla JS + Leaflet/OSM (`app.py:12` `create_app()`, `wsgi.py:1` `app` for gunicorn). Factory selects config via `FLASK_ENV` -> `config.py:44` `config_by_name` (`development`/`production`/`testing`).
- No `pyproject.toml`, no linter/typecheck. Only `requirements.txt:1` and `pytest` for verification.

## Commands (exact)
```bash
source .venv/bin/activate  # repo uses .venv (3.14); README also mentions venv/env — all work via run_gui.py:22
pip install -r requirements.txt
flask --app app init-db     # creates 5 tables per utils/db.py:5 SCHEMA
flask --app app seed        # seeds 7 centers (6 active +1 archived), 12 hotlines, admin, weather_cache — utils/seed.py:7
flask --app app run --debug # :5000; or python wsgi.py
gunicorn wsgi:app            # prod — Procfile:1, Render/PythonAnywhere entry
python run_gui.py            # demo launcher: auto-creates venv, init-db+seed if missing, opens browser :5000 — handles VENV_CANDIDATES .venv/venv//tmp/ligtas_venv/env
pytest -q                                    # 15 tests
pytest -q tests/test_sprint1.py::test_api_centers_returns_6  # single test (pattern: pytest -q <file>::<name>)
```

## Architecture
- `app.py:56` registers 4 blueprints: `routes/public.py` (`/`, `/map`, `/centers`, `/centers/<id>`, `/weather`, `/hotlines`), `routes/auth.py` (`/admin/login|logout`), `routes/admin.py` (`/admin/dashboard|centers|hotlines` + `utils/security.py:4` `login_required`), `routes/api.py` (`/api/centers`, `/api/centers/<id>`, `/api/hotlines`, `/api/weather`). API blueprint is CSRF-exempt (`app.py:68`).
- `services/weather_service.py:75` `fetch_weather` order: cache `<10min` -> OpenWeather (if key set and not placeholder) -> Open-Meteo (no key) -> stale cache `<1h` -> `503`. Never fabricates data; `api/weather` validates lat/lng `routes/api.py:89`.
- `utils/db.py:92` `get_db()`: `:memory:` in `TestingConfig` maps to `file:memdb_sprint1?mode=memory&cache=shared` (shared conn stored on `app._memory_db`). File DB uses `PRAGMA foreign_keys=ON` + `journal_mode=WAL`. Close avoids closing shared memory DB (`utils/db.py:115`).
- `config.py:8` env: `SECRET_KEY` (falls back to dev string — `ProductionConfig.validate()` called in `app.py:21-23` when `FLASK_ENV=production`; also validates `ADMIN_USERNAME`/`ADMIN_PASSWORD` non-default), `DATABASE_URL` -> `DATABASE` (default `instance/ligtas.sqlite`), `OPENWEATHER_API_KEY`, `GEMINI_API_KEY` (reserved Sprint 2, unused). `.env.example` no longer advertises `WEATHER_GOV`; admin creds documented in `README.md:33`.

## DB & Seed Notes
- Schema in `utils/db.py:5` — 5 tables, CHECK constraints on lat/lng, capacity, status enums. `archived` flag = soft delete (API filters `archived=0`).
- `seed` re-runs `init_db()` internally (`app.py:51`), safe to call `flask --app app seed` alone; idempotent (checks `SELECT 1` before insert).
- `instance/` and `*.sqlite` are gitignored — DB not persisted in repo. Delete `instance/ligtas.sqlite` to reset.

## Testing Quirks
- `config.py:38` `TestingConfig`: `DATABASE=":memory:"`, `WTF_CSRF_ENABLED=False`, `RATELIMIT_ENABLED=False`. Fixture `tests/test_sprint1.py:7` calls `create_app("testing")` + `init_db()` + `seed_db()` per session.
- Occupancy helpers computed in routes (`pct`, `available_slots`, `occupancy_status` thresholds `Available<80/Nearly 80-99/Full` — `routes/api.py:29`, `routes/public.py:41`).
- No CI workflows (`.github/` missing), no pre-commit. Verification is `pytest -q` only.

## Gotchas
- `run_gui.py:47` `ensure_venv()` re-execs with first valid venv python; if no venv it auto-creates `./venv` and installs. Headless/WSL: browser won't open — visit `http://127.0.0.1:5000` manually.
- Port 5000 busy: `flask --app app run --port 5001`. DB locked: `Ctrl+C` then `flask --app app init-db && flask --app app seed`.
- `externally-managed-environment` on system Python: always use venv.
- `api.weather.gov` is US-only — PH returns empty (gracefully handled, falls to 503 with `retry:true`).

## Conventions
- Branch `main` tracks `origin/main` (`git config`); remote `https://github.com/Makusu10/LigtasPH.git`.
- Templates in `templates/{public,admin,errors,partials}`; static tokens in `static/css/main.css` (`#155EEF` etc.).
- `models/__init__.py` is placeholder — query via `utils.db.get_db()`, not models.

## Agent Skills (OpenCode)

This project uses skills installed under `.opencode/skills/` (or a compatible path).

### Core Rules

- If a task matches a skill, invoke it with the `skill` tool before acting.
- Skills are located in `.opencode/skills/<skill-name>/SKILL.md`.
- Follow the skill workflow strictly; do not partially apply it.
- Never skip required steps such as spec, plan, or test when a skill demands them.

### Intent → Skill Mapping

Map the user's intent to the matching skill automatically:

- Feature / new functionality → `spec-driven-development`, then `incremental-implementation` and `test-driven-development`
- Planning / breakdown → `planning-and-task-breakdown`
- Bug / failure / unexpected behavior → `debugging-and-error-recovery`
- Code review → `code-review-and-quality`
- Refactoring / simplification → `code-simplification`
- API or interface design → `api-and-interface-design`
- UI work → `frontend-ui-engineering`

### Execution Model

For every request:

1. Determine if any skill applies (even a small chance).
2. Load the skill with `skill({ name: "<skill-name>" })`.
3. Follow the skill workflow exactly.
4. Only proceed to implementation once required steps are complete.
