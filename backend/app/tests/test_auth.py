import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_api_key_setting():
    original_api_key = settings.api_key
    original_jwt_secret = settings.jwt_secret
    settings.api_key = ""
    settings.jwt_secret = ""
    yield
    settings.api_key = original_api_key
    settings.jwt_secret = original_jwt_secret


def test_protected_route_allows_when_api_key_not_configured():
    response = client.post(
        "/blueprints/validate",
        json={
            "name": "auth-open",
            "schema_version": "1.0",
            "networks": [{"name": "net1"}],
            "nodes": [{"name": "node1", "networks": ["net1"]}],
        },
    )
    assert response.status_code == 200


def test_protected_route_requires_api_key_when_configured():
    settings.api_key = "secret-key"
    response = client.post(
        "/blueprints/validate",
        json={
            "name": "auth-required",
            "schema_version": "1.0",
            "networks": [{"name": "net1"}],
            "nodes": [{"name": "node1", "networks": ["net1"]}],
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHORIZED"


def test_protected_route_accepts_valid_api_key():
    settings.api_key = "secret-key"
    response = client.post(
        "/blueprints/validate",
        headers={"x-api-key": "secret-key"},
        json={
            "name": "auth-valid",
            "schema_version": "1.0",
            "networks": [{"name": "net1"}],
            "nodes": [{"name": "node1", "networks": ["net1"]}],
        },
    )
    assert response.status_code == 200
