"""GH issue #7: dataset provenance pinning + bounded serving drills.

Shared-DB rules (see AGENTS.md): the testing DB persists across files, so
every test here uses unique PROBE7- names and restores rows + meta keys it
touches. Assertions are delta-based, never absolute counts.
"""
import hashlib
import json

from app import create_app, geojson_import_action
from scripts.import_evac_centers import DEFAULT_PATH, import_geojson
from utils.db import get_db, get_meta, init_db, set_meta
from utils.seed import seed_db

PREFIX = "PROBE7-DRILL"


def _app():
    app = create_app("testing")
    with app.app_context():
        init_db()
        seed_db()
    return app


def _feature(name, lon=121.0, lat=14.6, municipality="City of Manila",
             prov="testprov", verified=False, needs_review=False):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "name": name,
            "municipality_input": municipality,
            "barangay_resolved": "Probe Barangay",
            "facility_type": "School",
            "facility_status": "Active",
            "geocode_provider": prov,
            "confidence": "high",
            "verified": verified,
            "needs_review": needs_review,
            "review_reason": "drill" if needs_review else "",
        },
    }


def _write(tmp_path, features):
    p = tmp_path / "probe.geojson"
    p.write_text(json.dumps({"type": "FeatureCollection",
                             "features": features}), encoding="utf-8")
    return str(p)


def _cleanup(app, names):
    with app.app_context():
        db = get_db()
        for n in names:
            db.execute("DELETE FROM evacuation_centers WHERE name=?", (n,))
        db.execute("DELETE FROM staging_centers WHERE name IN (%s)" %
                   ",".join("?" * len(names)), names)
        db.commit()


def test_import_records_sha256_in_stats_and_meta(tmp_path):
    app = _app()
    names = [f"{PREFIX}-SHA"]
    path = _write(tmp_path, [_feature(names[0])])
    with app.app_context():
        db = get_db()
        prev = {k: get_meta(db, k) for k in
                ("geojson.sha256", "geojson.imported_at", "geojson.build_id")}
        try:
            stats = import_geojson(db, path)
            expected = hashlib.sha256(open(path, "rb").read()).hexdigest()
            assert stats["dataset_sha256"] == expected
            set_meta(db, "geojson.sha256", stats["dataset_sha256"])
            set_meta(db, "geojson.imported_at", "drill")
            set_meta(db, "geojson.build_id", "drill")
            db.commit()
            assert get_meta(db, "geojson.sha256") == expected
        finally:
            with app.app_context():
                db2 = get_db()
                for k, v in prev.items():
                    set_meta(db2, k, v)
                db2.commit()
            _cleanup(app, names)


def test_reimport_is_refresh_only_and_preserves_admin_numbers(tmp_path):
    app = _app()
    name = f"{PREFIX}-REFRESH"
    path = _write(tmp_path, [_feature(name, lon=121.0)])
    try:
        with app.app_context():
            s1 = import_geojson(get_db(), path)
            assert s1["imported"] == 1
            get_db().execute(
                "UPDATE evacuation_centers SET capacity=500, "
                "current_occupancy=100 WHERE name=?", (name,))
            get_db().commit()
        # v2: moved pin + tampered flags — refresh must take geo fields only
        path = _write(tmp_path, [_feature(name, lon=122.0, prov="evilprov",
                                          verified=True)])
        with app.app_context():
            s2 = import_geojson(get_db(), path)
            assert s2["imported"] == 0 and s2["updated"] == 1
            assert s2["dataset_sha256"] != s1["dataset_sha256"]
            row = get_db().execute(
                "SELECT * FROM evacuation_centers WHERE name=?",
                (name,)).fetchone()
            assert row["lng"] == 122.0  # geo refreshed
            assert row["capacity"] == 500  # admin numbers preserved
            assert row["current_occupancy"] == 100
    finally:
        _cleanup(app, [name])


def test_import_action_decisions(tmp_path):
    app = _app()
    with app.app_context():
        db = get_db()
        prev = get_meta(db, "geojson.sha256")
        try:
            set_meta(db, "geojson.sha256", "")
            db.commit()
            _, _, action = geojson_import_action(db, None)
            assert action == "import"
            real_sha = hashlib.sha256(DEFAULT_PATH.read_bytes()).hexdigest()
            set_meta(db, "geojson.sha256", real_sha)
            db.commit()
            cur, rec, action = geojson_import_action(db, None)
            assert action == "skip" and cur == rec == real_sha
            set_meta(db, "geojson.sha256", "0" * 64)
            db.commit()
            cur, rec, action = geojson_import_action(db, None)
            assert action == "refresh" and rec == "0" * 64
        finally:
            set_meta(db, "geojson.sha256", prev)
            db.commit()


def test_tainted_name_drill_served_raw_over_json(tmp_path):
    # Data layer stays honest (raw JSON is not HTML); the render layer
    # neutralizes it — proven by the test_xss.py node drill on esc().
    app = _app()
    evil = f"{PREFIX}-<img src=x onerror=alert(1)>"
    path = _write(tmp_path, [_feature(evil)])
    try:
        with app.app_context():
            stats = import_geojson(get_db(), path)
            assert stats["imported"] == 1
        rows = app.test_client().get(
            "/api/centers", query_string={"q": PREFIX, "limit": 1000}).get_json()
        data = rows["data"] if isinstance(rows, dict) else rows
        hit = [r for r in data if r["name"] == evil]
        assert len(hit) == 1  # served, byte-faithful, for esc() to neutralize
    finally:
        _cleanup(app, [evil])


def test_default_list_bounded_with_pagination_metadata():
    app = _app()
    client = app.test_client()
    names = [f"{PREFIX}-BULK-{i:03d}" for i in range(60)]
    with app.app_context():
        db = get_db()
        total_before = int(client.get("/api/centers/version").get_json()["count"])
        try:
            for i, n in enumerate(names):
                db.execute(
                    "INSERT INTO evacuation_centers (name, address, city, lat, lng)"
                    " VALUES (?,?,?,?,?)",
                    (n, f"{n} addr", "Manila", 14.6, 121.0 + i * 0.0001))
            db.commit()
            r = client.get("/api/centers")
            assert len(r.get_json()) == 50  # bounded default
            assert int(r.headers["X-Total-Count"]) == total_before + 60
            assert r.headers["X-Page"] == "1"
            full = client.get("/api/centers", query_string={"limit": 1000})
            assert len(full.get_json()) == total_before + 60
        finally:
            for n in names:
                db.execute("DELETE FROM evacuation_centers WHERE name=?", (n,))
            db.commit()


def test_list_carries_dataset_provenance_headers():
    r = _app().test_client().get("/api/centers")
    assert "X-Dataset-Sha256" in r.headers
    assert "X-Dataset-Imported-At" in r.headers
