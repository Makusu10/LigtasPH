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
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_home_has_splash_cover(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="splash"' in html
    assert "ligtasph_splash_seen" in html
    assert "splash-hide" in html


def test_other_pages_have_no_splash(client):
    for page in ("/map", "/centers", "/weather", "/hotlines"):
        r = client.get(page)
        assert r.status_code == 200
        assert 'id="splash"' not in r.get_data(as_text=True)
