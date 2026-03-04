import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_api_key_setting():
    original = settings.api_key
    settings.api_key = ""
    yield
    settings.api_key = original


def test_list_mitre_techniques_returns_builtin_pack():
    response = client.get("/mitre/techniques")
    assert response.status_code == 200

    body = response.json()
    assert "items" in body
    technique_ids = {item["technique_id"] for item in body["items"]}
    assert {"T1566", "T1110", "T1041"}.issubset(technique_ids)


def test_list_mitre_techniques_requires_auth_when_api_key_configured():
    settings.api_key = "secret-key"

    unauthorized = client.get("/mitre/techniques")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["detail"]["code"] == "UNAUTHORIZED"

    authorized = client.get("/mitre/techniques", headers={"x-api-key": "secret-key"})
    assert authorized.status_code == 200
