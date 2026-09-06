# LigtasPH — Shared Progress & Context

> **Who this is for:** the human team *and* every AI tool working on this repo
> (OpenCode, Claude Code, Gemini CLI, Codex, Cursor — pick your harness).
> **Rule:** any tool or human that merges to `main` updates this file in the
> same push: move finished items to *Recent milestones*, add new gaps to
> *Up next*. Keep it short and factual — deep technical detail lives in
> `AGENTS.md` (agents) and `README.md` (humans).

## Snapshot (2026-09-06)

- Stack: Flask 3.x + SQLite + vanilla JS + Leaflet/OSM, Mapbox 2D/3D when `MAPBOX_TOKEN` is set.
- Entry: `run_gui.py` (dev launcher) / `wsgi.py` (prod). `pytest`: **214 passing**.
- Auth posture (GH #3 fixed): `/admin/login` is the canonical **public** login path; the old obscure path is a byte-identical alias on the same view. Bad creds → uniform `401` generic; 5 fails → `429` generic for 15 min (no 403 oracle). Lockout-DoS on the single admin account is a documented residual risk.
- API contract: standardized error envelope (`error` + `code` + `retry`; see `utils/api_errors.py`), shared validators (`utils/validation.py`), OpenAPI 3.1 spec at `static/openapi.yaml` served from `/api/openapi.yaml`.
- Branch model: feature branches → `main`. Live branches have included `JOSH`, `Kus`, `STEVEN` (check `git branch -a`; delete merged ones).
- AI design tooling: Impeccable skill installed **local-only** (gitignored `.opencode/` etc.) — never commit harness dirs.

## Feature inventory (verified against routes + templates)

### Public pages
- `/` **Home** — announcement banner (expandable, dismissible) + 🔔 history bell (newest-first, incl. expired); hero city picker + Use-my-location deep-linking to `/map?city=`; honest stat cards (Available / Nearly Full / Full / **Status Unknown** — NULL-capacity centers never counted as Available); map preview with count link; weather summary (saved location → city → labeled default) with loading/error states; red danger strip + `tel:` emergency links.
- `/map` **Evacuation Map** — Mapbox 2D/3D (GPS, fullscreen, POI tap-to-route, turn-by-turn dock) with OSM/Leaflet fallback; center/hazard/fire/quake overlays; Project NOAH flood/landslide/storm-surge layers; side-panel tabs (Centers / Hazards / Routes / Group); `?city=` deep-link hydration; solid glass nav overlay (readable over tiles, both themes).
- `/centers` **Directory** — search + city/status/sort filters, live 15s refresh with stamp, `?city=` + `?status=` deep links, `Status Unavailable` option.
- `/centers/<id>` **Center detail** — occupancy math, supply statuses.
- `/weather` — OpenWeather → Open-Meteo fallback (never fabricates; 503 + `retry:true` offline); heat index (Rothfusz/PAGASA bands), DENR AQI + US AQI kept separate, hourly strip; dark-mode contrast pass done.
- `/hotlines` — 29 seeded hotlines (12 LGU-verified + 17 from public directory, honestly labeled unverified), city/category/search filters.
- `/settings` — System/Light/Dark theme (whole UI incl. admin, pre-paint, no flash); location permission state + set/clear; announcement master switch + city + re-show dismissed; read-only provider status; clear-cached-data; server build stamp.

### Announcements system
- Admin composes **all / city / radius** banners with time windows (typed in PH time, stored UTC) and severity.
- Public: blocking modal on all pages **except home** (home uses banner + bell instead); acknowledge-to-dismiss persisted per device; offline-capable via cached feed; master kill-switch in Settings.
- Feed ordered **latest-first**; `?history=1` adds expired rows newest-first for the bell; title-echo stripped at display time; critical never truncated.
- 5 demo announcements ship in `utils/seed.py` (insert-missing, clearly demo).

### Admin (`/admin/*`, login + rate limits + lockout)
- **Dashboard** — totals, stale-center watchlist.
- **Centers** — full CRUD (occupancy/supply/status validated), archive/restore, audit trail in `center_status_updates`.
- **Hotlines** — add + archive/restore, category enum enforced.
- **Announcements** — publish (PH-time inputs), enable/disable, delete; list shows Manila times.
- **API Keys** — masked provider keys (`OPENWEATHER`, `MAPBOX pk.*`, `FIRMS`, `GEMINI`), empty-keeps-current, applied live; login/`SECRET_KEY` stay file-only.
- **Restart button** — re-execs dev server so updates reflect; refused under gunicorn/waitress (redeploy there); clients detect the new `build_id` via `/api/status` and refresh caches.

### APIs & services
- Centers (+`version` poll, detail; `?page=`/`?per_page=` pagination with `X-Total-Count`/`X-Page`/`X-Per-Page`/`X-Total-Pages` headers, opt-in JSON envelope via `?envelope=1` or `Accept: application/vnd.ligtasph.v2+json`), hotlines (same pagination scheme), NCR LGUs, weather, air-quality, environment (overall status = worst of heat/AQI), announcements (+history), earthquakes (USGS), fires (FIRMS, 503 without key), status (build id + provider booleans, **never secret values**), OpenAPI spec (`/api/openapi.yaml`).
- Emergency **group location sharing**: create group → invite code → post expiring pins → poll. POSTs accept `Idempotency-Key` header (24h `idempotency_keys` table, same-key+same-body replays cached response, same-key+new-body → `422`); pin upsert is an atomic `ON CONFLICT(group_id, display_name)` UPSERT with a matching UNIQUE index (init-time dedupe of legacy dupes).
- Emergency **group location sharing**: create group → invite code → post expiring pins → poll.
- `import-geojson` CLI for bulk center loads; `init-db`/`seed` idempotent (re-runnable; seed backfills without dupes).
- Startup self-heals stale DB schemas; no-cache headers on dynamic HTML/JSON (kills stale-page syndrome on phones).
- Bootstrapping: empty DBs seed demo data, then auto-import `data/ncr_evacuation_centers.geojson` once (idempotent) — ephemeral hosts like Render free tier serve the full ~857 centers, never just the 20 demo rows.
- Client sync: announcements feed + home banner/bell revalidate every 5 min while visible (`LigtasPrefs.SYNC_MS`); brand-new critical banners interrupt with a modal, others wait silently. Weather re-fetches the current view silently on the same cadence; hotlines reload too. Centers/map use a faster 15s version poll.
- Offline + cache-busting (from `gui-testing`): `static_asset()` boot-timestamp suffix on all local CSS/JS (no manual `?v=`); `/sw.js` service worker (map shell + datasets + Mapbox tiles cached, **navigations stay network-first** so the no-store policy holds); `/api/evac-centers.geojson` full-dataset stream; `/api/centers/<id>/status` honest not-available telemetry point.

### Cross-cutting
- **Dark mode**: var-driven `[data-theme="dark"]` over the whole UI; contrast passes done for nav, map popups, weather cards, badges, flashes, announcement modal.
- **Offline honesty**: cached feeds + clear stale/offline states; no fabricated zeros anywhere.
- **Tests**: 239 pytest (incl. `tests/test_api_standardization.py`: error-envelope codes, pagination headers/envelope, idempotency replay/conflict, location UPSERT), plus settings/status/keys/banner/history/timezone suites. Windows note: suite assumes UTF-8 file reads (`encoding="utf-8"` fixed in `test_noah.py`).

## Recent milestones (newest first)
- **Legal + accessibility pass** — `/privacy`, `/terms`, `/cookies` pages (PH Data Privacy Act-grounded, accurate to actual data flows) linked from the footer; no consent banner needed (strictly-necessary session cookie only, no analytics/trackers — documented with reasoning); full OSM/CARTO attribution; labeled filter controls; mobile-menu Esc + aria-expanded; Lucide icons hidden from AT; map tablist arrow keys; repaired malformed Join button; contrast tokens verified by computed ratio (muted 5.01/6.91, badges 6.12/6.01, primary buttons 5.48); `.btn` 44px floor; hero “official” qualified to “listed”; operator details left as explicit TODOs (never fabricated). `tests/test_legal.py` (12 tests). Note: `test_auth_paths.py::test_bad_password_uniform_across_both_paths` flaked twice (shared-DB lockout state) then passed 4 consecutive full runs incl. subsets — watch item, not a code defect found.
- **GH #7 refuse-gate** — changed-file boot import is now REFUSED (was flag-only): mismatch records `geojson.pending_sha256`, ingests nothing, serves old rows; approve via admin dashboard banner + `/admin/dataset/approve` POST or `import-geojson` CLI (both record the hash + clear pending); `pending_sha256` surfaced in `/api/status` dataset block. `q` LIKE wildcards escaped; boot import takes a best-effort file lock (`utils/import_lock.py`, fail-open). Load drill `scripts/load_drill_centers.py` (scratch DB, 50 concurrent): 0 errors, default page p50 3.3s/p95 3.7s, full export p50 3.5s/p95 4.0s — serialization-bound (per-request visits writes + GIL on one SQLite file; follow-up, not a regression). `tests/test_import_provenance.py` +7 (refuse/skip/approve/banner/wildcards/lock). 220 → 227 passing.
- **GH #5 SW staleness** — `/sw.js` version stamped with build id (auto-retires old caches, `no-store` on the script, fail-loud on missing placeholder); install gate refuses dataset bodies without `X-Dataset-Sha256`; offline map banner (`role=alert`, dated PHT from last good fetch, DRRMO wording, `textContent`-only); README ops runbook for cache scope/purge. `test_offline_infra.py` +4 (incl. node banner drill). 210 → 214 passing.
- **GH #7 supply-chain pinning** — `threat-modeling` decision (flag-not-refuse, daemon-thread boot, bounded default): sha256 pin in `app_meta` (recorded by boot + CLI, `X-Dataset-Sha256/Imported-At` on list, sha on GeoJSON), `geojson_import_action()` unit-testable, hash change → WARNING + refresh-only; `/api/centers` default 50 rows (explicit `?limit=1000` in map/directory/home/settings); `tests/test_import_provenance.py` (6 drills incl. tainted-name + admin-numbers-preserved). Live-fire: cold boot returns in 0.01s, 836 rows + meta recorded. 204 → 210 passing.
- **GH #4 export hardening** — `api-authorization-review` findings API-001–003 fixed: `/api/centers` list strips provenance internals (full row stays on detail); `/api/evac-centers.geojson` serves display fields only (mtime-gated in-memory strip, ETag + 304, `no-store`, `X-Dataset-Build`/`X-Dataset-File-Mtime` for #5's banner); per-IP limits (120/min list, 30/min export). OpenAPI contract updated. `tests/test_api_exposure.py` (5 tests). 199 → 204 passing.
- **GH #6 XSS hardening** — `secure-code-review` audit of all `templates/public/*.html` sinks (SCR-001 directory cards, SCR-002 hotline cards incl. `tel:` hrefs, SCR-003 reflected city echo in weather errors, SCR-004/005 env + home strings, SCR-006 `esc()` missing `'`); all routed through `esc()` (now with `&#39;`); map popups/steps/suggest verified already-escaped. `tests/test_xss.py` (6 tests: static sink scan + live node drill on shipped `esc()`). 193 → 199 passing.
- **GH #3 auth hardening** — threat-modeled login flow (TM-001 obscurity, TM-002 403 oracle, TM-003 lockout-DoS, TM-004 defaults); dual route (`/admin/login` canonical + alias, `url_for` resolves canonical); uniform 401/429 responses; `tests/test_auth_paths.py` (6 tests: parity, oracle, redirect, lockout); README runbook + AGENTS.md prose corrected. 187 → 193 passing.
- **API standardization** — `utils/api_errors.py` (`api_error` envelope: `error` + machine `code` + `retry`; codes `NOT_FOUND`/`INVALID_COORDINATES`/`INVALID_RADIUS`/`INVALID_DAYS`/`INVALID_ACCURACY`/`MISSING_REQUIRED_FIELDS`/`SERVICE_UNAVAILABLE`/`INTERNAL_ERROR`/`GROUP_CREATION_FAILED`/`PLACE_NOT_FOUND`), `utils/validation.py` (shared coordinate + pagination parsing), `utils/idempotency.py` (header-based replay guard on group/location POSTs), OpenAPI 3.1 contract (`static/openapi.yaml` + `/api/openapi.yaml`); `routes/api.py` fully converted, `tests/test_api_standardization.py` added (160 → 180 passing).
- Dismiss **undo** (10s toast restores banner/bell dismissals), 44px touch targets, dead splash CSS removed.
- `de5bb89` — Impeccable home refinement round 2 (operate hero, honest stats, severity text, PHT) + critique snapshot.
- `e96c1eb` — Dark-mode contrast fixes (map popups, floating nav).
- `c0ae2df` — Settings + dark mode, admin API keys + restart, home banner + bell history, 5 seeded announcements.
- `7d903e9` / `06a1f92` — README rewrite + runtime architecture chart.
- `13c43f2` — Map tile-error handler (CartoDB fallback).
- Mapbox 2D/3D GPS map, NOAH overlays + tabbed panel, NCR-wide search, admin CRUD + audit + POST logout, 17 national hotlines, Manila→UTC announcement times.

## Up next (gaps anyone may claim)
1. **Map page critique** — obvious next Impeccable target (preview interactivity, bell overlap, hero on 320px).
2. **Tagalog/Taglish microcopy** pass (homepage still English-only; affects trust).
3. **Real push notifications** (explicitly deferred; needs service worker + subscription backend).
4. **Map dark tiles** (deferred by decision; UI is dark, tiles stay light).
5. **FIRMS key** for dev (fires layer is 503 without it).

## AI-tool conventions
- Verify by execution: run `pytest -q` and boot the app before claiming done.
- New seed data must be insert-missing (shared `:memory:` test DB persists across files — use unique names / cleanup, never absolute counts).
- Never commit `.env`, `instance/`, venvs, or harness dirs (`.opencode/`, `.claude/`, `.gemini/`, `.agent/`).
- Frontend prefs live in `localStorage` under `ligtasph_*` keys — see `static/js/prefs.js` before adding new ones.
- Times: admins type **Manila**, DB/API store **UTC**, UI displays **PHT**.
