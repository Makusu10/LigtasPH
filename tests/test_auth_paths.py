"""GH issue #3: login path is public by design; auth responses are uniform.

Canonical path is /admin/login. The legacy obscure path is a byte-identical
alias. Bad credentials always yield 401 + the same generic message; locked
accounts yield 429 + generic wording (no 403/username-echo oracle).
"""
from app import create_app
from utils.db import get_db, init_db
from utils.seed import seed_db

ALIAS = "/hanapanngbaddieguardsimarkus"
CANONICAL = "/admin/login"

LOGIN = {"username": "admin", "password": "admin123"}
BAD = {"username": "admin", "password": "wrong"}


def _app():
    app = create_app("testing")
    with app.app_context():
        init_db()
        seed_db()
    return app


def _reset_lockout(app):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE administrators SET failed_attempts=0, locked_until=NULL")
        db.commit()


def test_canonical_login_page_ok():
    assert _app().test_client().get(CANONICAL).status_code == 200


def test_alias_login_page_ok():
    assert _app().test_client().get(ALIAS).status_code == 200


def test_bad_password_uniform_across_both_paths():
    app = _app()
    client = app.test_client()
    try:
        r1 = client.post(CANONICAL, data=BAD)
        r2 = client.post(ALIAS, data=BAD)
        assert r1.status_code == 401 == r2.status_code
        assert b"Invalid username or password." in r1.data
        assert r1.data == r2.data  # byte-identical alias behavior
        # unknown username yields the identical generic page (no oracle)
        r3 = client.post(CANONICAL, data={"username": "nosuchuser", "password": "wrong"})
        assert r3.status_code == 401
        assert r3.data == r1.data
    finally:
        # successful login resets failed_attempts so later suites start clean
        client.post(CANONICAL, data=LOGIN)


def test_canonical_login_valid_and_dashboard():
    client = _app().test_client()
    r = client.post(CANONICAL, data=LOGIN, follow_redirects=False)
    assert r.status_code == 302
    assert "/admin/dashboard" in r.headers["Location"]
    assert client.get("/admin/dashboard").status_code == 200


def test_unauth_redirect_targets_canonical_login():
    r = _app().test_client().get("/admin/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert CANONICAL in r.headers["Location"]
    assert ALIAS not in r.headers["Location"]


def test_lockout_returns_429_generic():
    app = _app()
    client = app.test_client()
    try:
        for _ in range(5):
            assert client.post(CANONICAL, data=BAD).status_code == 401
        r = client.post(CANONICAL, data=BAD)
        assert r.status_code == 429
        assert b"Too many failed attempts. Try again later." in r.data
        assert b"locked" not in r.data.lower()
    finally:
        _reset_lockout(app)
