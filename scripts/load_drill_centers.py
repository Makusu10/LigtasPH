#!/usr/bin/env python3
"""GH #7 acceptance load drill (stdlib only, scratch DB, never prod).

Spins a real WSGI server on an ephemeral port against a temp SQLite file
seeded + bulk-imported to ~856 rows, then fires 50 concurrent clients at
the default bounded page and 50 at the full ?limit=1000 export leg.
Reports p50/p95/error-rate/bytes per leg. Informational: numbers are
recorded in PROGRESS.md, nothing is asserted (timing tests are flaky).

Usage: venv\\Scripts\\python scripts/load_drill_centers.py
"""
import json
import os
import statistics
import sys
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

N_CLIENTS = 50


def build_scratch_db(path):
    os.environ["DATABASE_URL"] = path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import create_app
    from utils.db import init_db
    from utils.seed import seed_db
    app = create_app("development")
    with app.app_context():
        init_db()
        seed_db()
        from utils.db import get_db
        from scripts.import_evac_centers import import_geojson, DEFAULT_PATH
        stats = import_geojson(get_db(), str(DEFAULT_PATH))
    return app, stats


def serve(app):
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    port = srv.server_port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


def wait_ready(base, timeout=180):
    """Wait until the dataset settles (boot import thread finished)."""
    url = base + "/version"
    last = None
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                cur = json.loads(r.read()).get("count")
            if cur and cur == last:
                return cur
            last = cur
        except Exception:  # noqa: BLE001 — still booting
            pass
        time.sleep(2)
    raise RuntimeError("dataset never settled")


def volley(base, params, n=N_CLIENTS):
    def one(_):
        url = base + params
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                body = r.read()
            dt = (time.perf_counter() - t0) * 1000
            return dt, len(body), None
        except Exception as e:  # noqa: BLE001 — drill records, never raises
            return (time.perf_counter() - t0) * 1000, 0, repr(e)

    with ThreadPoolExecutor(max_workers=n) as ex:
        return list(ex.map(one, range(n)))


def report(name, rows):
    lat = sorted(r[0] for r in rows)
    errs = [r for r in rows if r[2] is not None]
    sizes = [r[1] for r in rows if r[2] is None]
    print(f"--- {name} (n={len(rows)}) ---")
    print(f"  errors : {len(errs)}")
    for e in errs[:3]:
        print(f"    {e[2]}")
    if lat:
        print(f"  p50    : {statistics.median(lat):8.1f} ms")
        print(f"  p95    : {statistics.quantiles(lat, n=100)[94]:8.1f} ms")
        print(f"  max    : {max(lat):8.1f} ms")
    if sizes:
        print(f"  bytes  : min={min(sizes)} p50={int(statistics.median(sizes))} max={max(sizes)}")


def main():
    tmp = tempfile.mkdtemp(prefix="ligtasph_drill_")
    db_path = os.path.join(tmp, "drill.sqlite")
    print(f"scratch db: {db_path}")
    app, stats = build_scratch_db(db_path)
    print(f"dataset: imported={stats.get('imported')} updated={stats.get('updated')} "
          f"quarantined={stats.get('quarantined')}")
    srv, port = serve(app)
    base = f"http://127.0.0.1:{port}/api/centers"
    try:
        n = wait_ready(base)
        print(f"dataset settled at {n} rows")
        urllib.request.urlopen(base + "?limit=1", timeout=30).read()  # warmup
        time.sleep(0.5)
        report("default bounded page (50 rows)", volley(base, ""))
        time.sleep(2)  # stay under the 120/min per-IP limit across legs
        report("full export (?limit=1000)", volley(base, "?limit=1000"))
    finally:
        srv.shutdown()
    print(f"scratch files left under {tmp} (delete manually)")


if __name__ == "__main__":
    main()
