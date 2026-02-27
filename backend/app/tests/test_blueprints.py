codex/verify-the-structure-kqxjtv
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.blueprint_store import blueprint_store
main

client = TestClient(app)


codex/verify-the-structure-kqxjtv
@pytest.fixture(autouse=True)
def clean_blueprint_store():
    blueprint_store.clear()
    yield
    blueprint_store.clear()


def _valid_payload():
    return {
        "name": "sample-lab",
        "version": "0.1.0",
main
        "networks": [{"name": "corp-net", "cidr": "10.10.10.0/24"}],
        "nodes": [{"name": "dc01", "role": "domain-controller", "networks": ["corp-net"]}],
    }

codex/verify-the-structure-kqxjtv

def test_validate_blueprint_success_response_shape():
    response = client.post("/blueprints/validate", json=_valid_payload())
    assert response.status_code == 200
main
    body = response.json()
    assert body == {
        "valid": True,
        "name": "sample-lab",
        "version": "0.1.0",
        "nodes": 1,
        "networks": 1,
    }


codex/verify-the-structure-kqxjtv
def test_blueprint_crud_lifecycle():
    create_response = client.post("/blueprints", json=_valid_payload())
    assert create_response.status_code == 200
    blueprint_id = create_response.json()["id"]

    list_response = client.get("/blueprints")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == blueprint_id

    get_response = client.get(f"/blueprints/{blueprint_id}")
    assert get_response.status_code == 200
    assert get_response.json()["blueprint"]["name"] == "sample-lab"

    delete_response = client.delete(f"/blueprints/{blueprint_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/blueprints/{blueprint_id}")
    assert missing_response.status_code == 404


def test_validate_blueprint_unknown_network_returns_400():
main
    payload = {
        "name": "invalid-lab",
        "networks": [{"name": "corp-net"}],
        "nodes": [{"name": "ws01", "networks": ["missing-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert "unknown networks" in response.json()["detail"]
codex/verify-the-structure-kqxjtv
main


def test_validate_blueprint_invalid_cidr():
    payload = {
        "name": "invalid-cidr-lab",
        "networks": [{"name": "corp-net", "cidr": "10.10.999.0/24"}],
        "nodes": [{"name": "ws01", "networks": ["corp-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert "invalid CIDR" in response.json()["detail"]


def test_validate_blueprint_node_without_network():
    payload = {
        "name": "orphan-node-lab",
        "networks": [{"name": "corp-net"}],
        "nodes": [{"name": "ws01", "networks": []}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert "must reference at least one network" in response.json()["detail"]
codex/verify-the-structure-kqxjtv
main
