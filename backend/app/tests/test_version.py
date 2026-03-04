from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "orion-range-core"
    assert payload["version"] == "0.1.0"
    assert payload["environment"]
