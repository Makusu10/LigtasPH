import pytest
from app import create_app
from utils.db import init_db
from utils.seed import seed_db


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        init_db()
        seed_db()
        from utils.db import get_db
        db = get_db()
        # Shared in-memory DB persists across tests in one process — reset
        # our rows so each test sees exactly one copy.
        db.execute("DELETE FROM announcements WHERE title IN ('Old news', 'Fresh alert')")
        db.execute(
            """INSERT INTO announcements (title, message, scope, severity, starts_at, ends_at)
               VALUES ('Old news', 'expired msg', 'all', 'info', '2000-01-01 00:00:00', '2000-01-02 00:00:00')"""
        )
        db.execute(
            """INSERT INTO announcements (title, message, scope, severity, starts_at, ends_at)
               VALUES ('Fresh alert', 'live msg', 'all', 'critical', '2000-01-01 00:00:00', '2100-01-01 00:00:00')"""
        )
        db.commit()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client):
    client.post("/hanapanngbaddieguardsimarkus", data={"username": "admin", "password": "admin123"})


def test_home_has_banner_and_bell(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="home-ann-banner"' in html
    assert 'id="home-ann-expand"' in html
    assert 'id="home-ann-dismiss"' in html
    assert 'id="ann-bell"' in html
    assert 'id="ann-history"' in html
    assert "js/home_banner.js" in html
    assert 'id="heroCity"' in html
    assert 'id="heroFind"' in html
    assert 'id="home-ann-sev"' in html
    assert 'tel:911' in html


def test_home_unknown_stat_for_null_capacity(client, app):
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute("DELETE FROM evacuation_centers WHERE name='Nullcap Test'")
        db.execute(
            """INSERT INTO evacuation_centers (name, address, city, lat, lng, capacity, current_occupancy)
               VALUES ('Nullcap Test', 'Addr', 'Marikina', 14.6, 121.1, NULL, NULL)""")
        db.commit()
    try:
        html = client.get("/").get_data(as_text=True)
        assert "Status Unknown" in html
    finally:
        with app.app_context():
            from utils.db import get_db
            db = get_db()
            db.execute("DELETE FROM evacuation_centers WHERE name='Nullcap Test'")
            db.commit()


def test_api_history_includes_expired_newest_first(client):
    data = client.get("/api/announcements?history=1").get_json()
    # Other test files share this DB — filter to our rows, keep order.
    ours = [a for a in data if a["title"] in ("Fresh alert", "Old news")]
    assert [a["title"] for a in ours] == ["Fresh alert", "Old news"]  # starts_at DESC
    by_title = {a["title"]: a for a in ours}
    assert by_title["Old news"]["expired"] == 1
    assert by_title["Fresh alert"]["expired"] == 0


def test_api_live_still_excludes_expired(client):
    titles = [a["title"] for a in client.get("/api/announcements").get_json()]
    assert "Fresh alert" in titles
    assert "Old news" not in titles


def test_admin_times_stored_as_utc(client, app):
    # Admin types Philippine time (UTC+8); DB keeps UTC for the API.
    _login(client)
    r = client.post("/admin/announcements", data={
        "title": "TZ check", "message": "tz", "scope": "all", "severity": "info",
        "starts_at": "2026-09-05T08:00", "ends_at": "2026-09-05T12:00",
    })
    assert r.status_code == 302
    with app.app_context():
        from utils.db import get_db
        row = get_db().execute(
            "SELECT starts_at, ends_at FROM announcements WHERE title='TZ check'").fetchone()
        assert row["starts_at"] == "2026-09-05 00:00:00"
        assert row["ends_at"] == "2026-09-05 04:00:00"
    # Admin list shows the Manila times back.
    assert "2026-09-05 08:00 → 2026-09-05 12:00" in client.get("/admin/announcements").get_data(as_text=True)


def test_api_live_latest_first_regardless_of_severity(client, app):
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute(
            """INSERT INTO announcements (title, message, scope, severity, starts_at, ends_at)
               VALUES ('Newer info', 'live', 'all', 'info', '2020-01-01 00:00:00', '2100-01-01 00:00:00')""")
        db.commit()
    titles = [a["title"] for a in client.get("/api/announcements").get_json()]
    assert titles.index("Newer info") < titles.index("Fresh alert")


def test_dedup_message_strips_title_echo():
    from utils.announcements import dedup_message
    t = 'Genshin Impact Version 7.0 "Everwinter Without Mercy"'
    assert dedup_message(t, t + ' officially launched on August 12, 2026, introducing Snezhnaya.') == \
        'officially launched on August 12, 2026, introducing Snezhnaya.'
    assert dedup_message(t, '"Genshin impact version 7.0 "everwinter without mercy"" — patch notes here.') == \
        'patch notes here.'
    assert dedup_message('Update', 'Darkmode tsaka may banner.') == 'Darkmode tsaka may banner.'
    assert dedup_message('Hello', 'Hello') == 'Hello'  # never blank the message
    assert dedup_message('', 'Something') == 'Something'
    assert dedup_message('T', None) is None


def test_api_feed_dedups_title_echo(client, app):
    with app.app_context():
        from utils.db import get_db
        db = get_db()
        db.execute("DELETE FROM announcements WHERE title='Echo test'")
        db.execute(
            """INSERT INTO announcements (title, message, scope, severity, starts_at, ends_at)
               VALUES ('Echo test', 'Echo test: body here', 'all', 'info', '2021-01-01 00:00:00', '2100-01-01 00:00:00')""")
        db.commit()
    data = client.get("/api/announcements?history=1").get_json()
    row = next(a for a in data if a["title"] == "Echo test")
    assert row["message"] == "body here"
    # Stored row untouched.
    with app.app_context():
        from utils.db import get_db
        stored = get_db().execute("SELECT message FROM announcements WHERE title='Echo test'").fetchone()["message"]
        assert stored == "Echo test: body here"

