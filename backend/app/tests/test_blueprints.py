from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_validate_blueprint_success():
    payload = {
        "name": "sample-lab",
        "version": "0.1",
        "networks": [{"name": "corp-net", "cidr": "10.10.10.0/24"}],
        "nodes": [{"name": "dc01", "role": "domain-controller", "networks": ["corp-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_validate_blueprint_unknown_network():
    payload = {
        "name": "invalid-lab",
        "networks": [{"name": "corp-net"}],
        "nodes": [{"name": "ws01", "networks": ["missing-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert "unknown networks" in response.json()["detail"]
