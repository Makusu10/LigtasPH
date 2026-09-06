import datetime
import pytest
from app import create_app
from utils.db import init_db, get_db
from utils.seed import seed_db


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        init_db()
        seed_db()
        # These tests assume a clean announcements table; seed rows and
        # other files' rows share this in-memory DB, so reset it here.
        get_db().execute("DELETE FROM announcements")
        get_db().commit()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    client.post("/hanapanngbaddieguardsimarkus", data={"username": "admin", "password": "admin123"})


def test_api_announcements_empty(client):
    r = client.get("/api/announcements")
    assert r.status_code == 200
    assert r.get_json() == []


def test_api_announcements_scopes_and_filtering(client, app):
    now = datetime.datetime.now(datetime.timezone.utc)
    s_past = (now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    e_future = (now + datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    e_past = (now - datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    with app.app_context():
        db = get_db()
        # 1. Global active announcement
        db.execute(
            """INSERT INTO announcements
               (title, message, scope, severity, starts_at, ends_at, is_active)
               VALUES ('Global Alert', 'All residents be alert', 'all', 'critical', ?, ?, 1)""",
            (s_past, e_future),
        )
        # 2. City scoped announcement (Marikina)
        db.execute(
            """INSERT INTO announcements
               (title, message, scope, city, severity, starts_at, ends_at, is_active)
               VALUES ('Marikina Flood', 'River level rising', 'city', 'Marikina', 'warning', ?, ?, 1)""",
            (s_past, e_future),
        )
        # 3. Radius scoped announcement (centered near Marikina 14.6308, 121.0968, 5km radius)
        db.execute(
            """INSERT INTO announcements
               (title, message, scope, center_lat, center_lng, radius_km, severity, starts_at, ends_at, is_active)
               VALUES ('Local Evac', 'Immediate evac in 5km', 'radius', 14.6308, 121.0968, 5.0, 'critical', ?, ?, 1)""",
            (s_past, e_future),
        )
        # 4. Inactive announcement
        db.execute(
            """INSERT INTO announcements
               (title, message, scope, severity, starts_at, ends_at, is_active)
               VALUES ('Draft', 'Hidden draft', 'all', 'info', ?, ?, 0)""",
            (s_past, e_future),
        )
        # 5. Expired announcement
        db.execute(
            """INSERT INTO announcements
               (title, message, scope, severity, starts_at, ends_at, is_active)
               VALUES ('Past Event', 'Already ended', 'all', 'info', ?, ?, 1)""",
            (s_past, e_past),
        )
        db.commit()

    # Query without params: should only receive global announcement
    r = client.get("/api/announcements")
    assert r.status_code == 200
    items = r.get_json()
    assert len(items) == 1
    assert items[0]["title"] == "Global Alert"

    # Query with city=Marikina: should get global + Marikina
    r_city = client.get("/api/announcements?city=Marikina")
    assert r_city.status_code == 200
    titles = [it["title"] for it in r_city.get_json()]
    assert "Global Alert" in titles
    assert "Marikina Flood" in titles
    assert "Local Evac" not in titles

    # Query with city=Quezon City: should only get global
    r_other = client.get("/api/announcements?city=Quezon+City")
    assert r_other.status_code == 200
    titles = [it["title"] for it in r_other.get_json()]
    assert titles == ["Global Alert"]

    # Query near center coords (within 5km): gets global + radius announcement
    r_near = client.get("/api/announcements?lat=14.6320&lon=121.0970")
    assert r_near.status_code == 200
    titles = [it["title"] for it in r_near.get_json()]
    assert "Global Alert" in titles
    assert "Local Evac" in titles
    assert "Marikina Flood" not in titles

    # Query far from coords (e.g. Davao ~900km away): only gets global
    r_far = client.get("/api/announcements?lat=7.1907&lon=125.4573")
    assert r_far.status_code == 200
    titles = [it["title"] for it in r_far.get_json()]
    assert titles == ["Global Alert"]


def test_api_announcements_invalid_coords(client):
    # Missing one coordinate
    r1 = client.get("/api/announcements?lat=14.6308")
    assert r1.status_code == 400
    assert "error" in r1.get_json()

    r2 = client.get("/api/announcements?lon=121.0968")
    assert r2.status_code == 400

    # Out of range coordinates
    r3 = client.get("/api/announcements?lat=999&lon=121.0968")
    assert r3.status_code == 400

    # Non-numeric
    r4 = client.get("/api/announcements?lat=abc&lon=def")
    assert r4.status_code == 400


def test_admin_announcements_crud(client, app):
    # Unauthenticated access redirects
    r = client.get("/admin/announcements")
    assert r.status_code == 302
    assert "/admin/login" in r.headers["Location"]

    _login(client)

    # Page renders ok
    r = client.get("/admin/announcements")
    assert r.status_code == 200
    assert b"Mass Banner Announcements" in r.data

    # Create new announcement
    post_data = {
        "title": "Drill Notice",
        "message": "Nationwide simultaneous earthquake drill tomorrow at 9 AM.",
        "scope": "all",
        "severity": "info",
        "starts_at": "2026-09-05T08:00",
        "ends_at": "2026-09-05T12:00",
    }
    r = client.post("/admin/announcements", data=post_data, follow_redirects=True)
    assert r.status_code == 200
    assert b"Announcement published." in r.data

    with app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM announcements WHERE title='Drill Notice'").fetchone()
        assert row is not None
        assert row["is_active"] == 1
        aid = row["id"]

    # Toggle active
    r = client.post(f"/admin/announcements/{aid}/toggle", follow_redirects=True)
    assert r.status_code == 200
    assert b"Announcement disabled." in r.data

    with app.app_context():
        db = get_db()
        row = db.execute("SELECT is_active FROM announcements WHERE id=?", (aid,)).fetchone()
        assert row["is_active"] == 0

    # Toggle back
    r = client.post(f"/admin/announcements/{aid}/toggle", follow_redirects=True)
    assert r.status_code == 200
    assert b"Announcement enabled." in r.data

    # Delete announcement
    r = client.post(f"/admin/announcements/{aid}/delete", follow_redirects=True)
    assert r.status_code == 200
    assert b"Announcement deleted." in r.data

    with app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM announcements WHERE id=?", (aid,)).fetchone()
        assert row is None


def test_admin_announcement_form_validation(client):
    _login(client)

    # Missing title
    r = client.post("/admin/announcements", data={
        "title": "", "message": "msg", "scope": "all",
        "starts_at": "2026-09-05T08:00", "ends_at": "2026-09-05T12:00",
    }, follow_redirects=True)
    assert b"Title is required." in r.data

    # End before start
    r = client.post("/admin/announcements", data={
        "title": "Bad Times", "message": "msg", "scope": "all",
        "starts_at": "2026-09-05T12:00", "ends_at": "2026-09-05T08:00",
    }, follow_redirects=True)
    assert b"End time must be after start time." in r.data

    # City scope without city
    r = client.post("/admin/announcements", data={
        "title": "No City", "message": "msg", "scope": "city", "city": "",
        "starts_at": "2026-09-05T08:00", "ends_at": "2026-09-05T12:00",
    }, follow_redirects=True)
    assert b"City is required for city-scoped announcements." in r.data

    # Radius scope without coordinates
    r = client.post("/admin/announcements", data={
        "title": "No Radius Coords", "message": "msg", "scope": "radius",
        "starts_at": "2026-09-05T08:00", "ends_at": "2026-09-05T12:00",
    }, follow_redirects=True)
    assert b"Center lat/lng and radius are required for radius scope." in r.data

