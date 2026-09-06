"""Community rain reports: anonymous ground truth with expiry."""
import pytest

from app import create_app
from utils.db import get_db, init_db
from utils.seed import seed_db

PREFIX = "PROBE7-RAIN"


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        init_db()
        seed_db()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _count(app):
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) c FROM rain_reports").fetchone()["c"]


def test_post_report_roundtrip(client, app):
    before = _count(app)
    r = client.post("/api/rain-reports", json={
        "intensity": "heavy", "flooding": "yes", "city": "Marikina",
        "lat": 14.6308, "lon": 121.0968,
    })
    assert r.status_code == 201
    assert r.get_json()["intensity"] == "heavy"
    assert _count(app) == before + 1
    with app.app_context():
        row = get_db().execute(
            "SELECT * FROM rain_reports ORDER BY id DESC LIMIT 1").fetchone()
        assert row["flooding"] == 1
        assert row["city"] == "Marikina"
        db = get_db()
        db.execute("DELETE FROM rain_reports WHERE id=?", (row["id"],))
        db.commit()


def test_post_rejects_bad_intensity(client, app):
    before = _count(app)
    r = client.post("/api/rain-reports", json={"intensity": "drizzle"})
    assert r.status_code == 400
    r = client.post("/api/rain-reports", json={})
    assert r.status_code == 400
    assert _count(app) == before


def test_post_rejects_bad_coords(client, app):
    before = _count(app)
    r = client.post("/api/rain-reports", json={"intensity": "light", "lat": 999, "lon": 999})
    assert r.status_code == 400
    r = client.post("/api/rain-reports", json={"intensity": "light", "lat": 14.6})
    assert r.status_code == 400  # half a position is not a position
    assert _count(app) == before


def test_flooding_only_counts_for_heavy(client, app):
    r = client.post("/api/rain-reports", json={"intensity": "light", "flooding": 1})
    assert r.status_code == 201
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM rain_reports ORDER BY id DESC LIMIT 1").fetchone()
        assert row["flooding"] is None
        db.execute("DELETE FROM rain_reports WHERE id=?", (row["id"],))
        db.commit()


def test_summary_aggregates_and_expires(client, app):
    with app.app_context():
        db = get_db()
        for intensity, flood in (("none", None), ("light", None), ("heavy", 1), ("heavy", 0)):
            db.execute(
                "INSERT INTO rain_reports (city, intensity, flooding) VALUES (?,?,?)",
                ("Marikina", intensity, flood))
        db.execute(
            "INSERT INTO rain_reports (city, intensity, reported_at) VALUES (?,?,datetime('now', '-5 hours'))",
            ("Marikina", "heavy"))
        db.commit()
    try:
        d = client.get("/api/rain-reports?city=Marikina").get_json()
        assert d["total"] == 4  # the 5-hour-old row expired out
        assert d["none"] == 1 and d["light"] == 1 and d["heavy"] == 2
        assert d["flooding"] == 1
        assert d["window_hours"] == 3
        all_d = client.get("/api/rain-reports").get_json()
        assert all_d["total"] >= 4
    finally:
        with app.app_context():
            db = get_db()
            db.execute("DELETE FROM rain_reports WHERE city=?", ("Marikina",))
            db.commit()


def test_summary_never_returns_individual_rows(client):
    d = client.get("/api/rain-reports").get_json()
    assert set(d) == {"city", "window_hours", "total", "none", "light",
                      "heavy", "flooding", "latest_at"}
    assert "lat" not in d and "lng" not in d
