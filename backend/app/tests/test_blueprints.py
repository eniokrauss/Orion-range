from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_validate_blueprint_success():
    payload = {
        "name": "sample-lab",
        "version": "0.1.0",
        "networks": [{"name": "corp-net", "cidr": "10.10.10.0/24"}],
        "nodes": [{"name": "dc01", "role": "domain-controller", "networks": ["corp-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["summary"] == {"nodes": 1, "networks": 1}


def test_validate_blueprint_unknown_network():
    payload = {
        "name": "invalid-lab",
        "networks": [{"name": "corp-net"}],
        "nodes": [{"name": "ws01", "networks": ["missing-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "BLUEPRINT_VALIDATION_ERROR"
    assert "unknown networks" in detail["message"]


def test_validate_blueprint_invalid_cidr():
    payload = {
        "name": "invalid-cidr-lab",
        "networks": [{"name": "corp-net", "cidr": "10.10.999.0/24"}],
        "nodes": [{"name": "ws01", "networks": ["corp-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert "invalid CIDR" in response.json()["detail"]["message"]


def test_validate_blueprint_node_without_network():
    payload = {
        "name": "orphan-node-lab",
        "networks": [{"name": "corp-net"}],
        "nodes": [{"name": "ws01", "networks": []}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert "must reference at least one network" in response.json()["detail"]["message"]
