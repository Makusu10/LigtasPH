import json
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


def test_standardized_error_envelope_404(client):
    r = client.get("/api/centers/999999")
    assert r.status_code == 404
    data = r.get_json()
    assert data["error"] == "Not found"
    assert data["code"] == "NOT_FOUND"
    assert data["retry"] is False
    assert isinstance(data["details"], dict)


def test_standardized_error_envelope_400(client):
    r = client.get("/api/weather?lat=999&lon=999")
    assert r.status_code == 400
    data = r.get_json()
    assert "error" in data
    assert data["code"] == "INVALID_COORDINATES"
    assert data["retry"] is False


def test_centers_backward_compatible_and_pagination(client):
    # Backward-compatible default: bare array with all centers
    r_default = client.get("/api/centers")
    assert r_default.status_code == 200
    data = r_default.get_json()
    assert isinstance(data, list)
    assert len(data) >= 20
    assert "X-Total-Count" in r_default.headers
    total = int(r_default.headers["X-Total-Count"])
    assert total >= 20

    # Paginated query
    r_paged = client.get("/api/centers?limit=5&page=1")
    assert r_paged.status_code == 200
    paged_data = r_paged.get_json()
    assert isinstance(paged_data, list)
    assert len(paged_data) == 5
    assert r_paged.headers["X-Total-Count"] == str(total)
    assert r_paged.headers["X-Page"] == "1"
    assert r_paged.headers["X-Per-Page"] == "5"

    # Envelope query
    r_env = client.get("/api/centers?limit=5&page=1&envelope=1")
    assert r_env.status_code == 200
    env_data = r_env.get_json()
    assert "data" in env_data
    assert len(env_data["data"]) == 5
    assert "pagination" in env_data
    assert env_data["pagination"]["page"] == 1
    assert env_data["pagination"]["pageSize"] == 5
    assert env_data["pagination"]["total"] == total


def test_hotlines_pagination(client):
    r_default = client.get("/api/hotlines")
    assert r_default.status_code == 200
    all_hotlines = r_default.get_json()
    assert isinstance(all_hotlines, list)
    total = len(all_hotlines)
    assert total > 0
    assert r_default.headers["X-Total-Count"] == str(total)

    # Paginate 3 items
    r_paged = client.get("/api/hotlines?limit=3&page=1")
    assert r_paged.status_code == 200
    assert len(r_paged.get_json()) == 3
    assert r_paged.headers["X-Per-Page"] == "3"


def test_atomic_location_upsert_and_casing(client):
    # Create group
    g = client.post("/api/groups", json={"name": "Family"}).get_json()
    code = g["invite_code"]

    # Initial pin
    r1 = client.post("/api/locations", json={
        "invite_code": code,
        "display_name": "markus",
        "lat": 14.65,
        "lon": 121.05,
    })
    assert r1.status_code == 201

    # Atomic update with new coordinates and updated casing
    r2 = client.post("/api/locations", json={
        "invite_code": code,
        "display_name": "MARKUS",
        "lat": 14.66,
        "lon": 121.06,
    })
    assert r2.status_code == 201

    # Verify single pin with updated coordinates and uppercase name
    locs = client.get(f"/api/groups/{code}/locations").get_json()
    assert len(locs) == 1
    assert locs[0]["display_name"] == "MARKUS"
    assert locs[0]["lat"] == pytest.approx(14.66)
    assert locs[0]["lon"] == pytest.approx(121.06)


def test_idempotency_key_group_creation(client):
    key = "test-idem-group-001"
    headers = {"Idempotency-Key": key}
    payload = {"name": "Barangay Watch"}

    # First attempt: creates group
    r1 = client.post("/api/groups", headers=headers, json=payload)
    assert r1.status_code == 201
    data1 = r1.get_json()
    code1 = data1["invite_code"]

    # Second identical attempt: returns cached response with same invite_code
    r2 = client.post("/api/groups", headers=headers, json=payload)
    assert r2.status_code == 201
    data2 = r2.get_json()
    assert data2["invite_code"] == code1
    assert data2["id"] == data1["id"]

    # Third attempt with same key but altered payload: fails with 422
    altered_payload = {"name": "Different Name"}
    r3 = client.post("/api/groups", headers=headers, json=altered_payload)
    assert r3.status_code == 422
    data3 = r3.get_json()
    assert data3["code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"


def test_openapi_spec_route(client):
    r = client.get("/api/openapi.yaml")
    assert r.status_code == 200
    assert "openapi: 3.1.0" in r.text
    assert "/api/centers:" in r.text
