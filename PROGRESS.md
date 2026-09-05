# LigtasPH — Shared Progress & Context

> **Who this is for:** the human team *and* every AI tool working on this repo
> (OpenCode, Claude Code, Gemini CLI, Codex, Cursor — pick your harness).
> **Rule:** any tool or human that merges to `main` updates this file in the
> same push: move finished items to *Recent milestones*, add new gaps to
> *Up next*. Keep it short and factual — deep technical detail lives in
> `AGENTS.md` (agents) and `README.md` (humans).

## Snapshot (2026-09-05)

- Stack: Flask 3.x + SQLite + vanilla JS + Leaflet/OSM, Mapbox 2D/3D when `MAPBOX_TOKEN` is set.
- Entry: `run_gui.py` (dev launcher) / `wsgi.py` (prod). `pytest`: **160 passing**.
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
- Centers (+`version` poll, detail), hotlines, NCR LGUs, weather, air-quality, environment (overall status = worst of heat/AQI), announcements (+history), earthquakes (USGS), fires (FIRMS, 503 without key), status (build id + provider booleans, **never secret values**).
- Emergency **group location sharing**: create group → invite code → post expiring pins → poll.
- `import-geojson` CLI for bulk center loads; `init-db`/`seed` idempotent (re-runnable; seed backfills without dupes).
- Startup self-heals stale DB schemas; no-cache headers on dynamic HTML/JSON (kills stale-page syndrome on phones).
- Client sync: announcements feed + home banner/bell revalidate every 5 min while visible (`LigtasPrefs.SYNC_MS`); brand-new critical banners interrupt with a modal, others wait silently. Weather re-fetches the current view silently on the same cadence; hotlines reload too. Centers/map use a faster 15s version poll.
- Offline + cache-busting (from `gui-testing`): `static_asset()` boot-timestamp suffix on all local CSS/JS (no manual `?v=`); `/sw.js` service worker (map shell + datasets + Mapbox tiles cached, **navigations stay network-first** so the no-store policy holds); `/api/evac-centers.geojson` full-dataset stream; `/api/centers/<id>/status` honest not-available telemetry point.

### Cross-cutting
- **Dark mode**: var-driven `[data-theme="dark"]` over the whole UI; contrast passes done for nav, map popups, weather cards, badges, flashes, announcement modal.
- **Offline honesty**: cached feeds + clear stale/offline states; no fabricated zeros anywhere.
- **Tests**: 160 pytest, incl. settings/status/keys/banner/history/timezone suites. Windows note: suite assumes UTF-8 file reads (`encoding="utf-8"` fixed in `test_noah.py`).

## Recent milestones (newest first)
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
