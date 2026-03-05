import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.blueprint_repository import blueprint_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_blueprint_repository():
    blueprint_repository.clear_all()
    yield
    blueprint_repository.clear_all()


def _valid_payload():
    return {
        "name": "sample-lab",
        "schema_version": "1.0",
        "version": "0.1.0",
        "networks": [{"name": "corp-net", "cidr": "10.10.10.0/24"}],
        "nodes": [{"name": "dc01", "role": "domain-controller", "networks": ["corp-net"]}],
    }


def test_validate_blueprint_success_response_shape():
    response = client.post("/blueprints/validate", json=_valid_payload())
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "valid": True,
        "name": "sample-lab",
        "schema_version": "1.0",
        "version": "0.1.0",
        "nodes": 1,
        "networks": 1,
    }


def test_blueprint_crud_lifecycle():
    create_response = client.post("/blueprints", json=_valid_payload())
    assert create_response.status_code == 200
    blueprint_id = create_response.json()["id"]

    list_response = client.get("/blueprints")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == blueprint_id
    assert list_response.json()[0]["schema_version"] == "1.0"

    get_response = client.get(f"/blueprints/{blueprint_id}")
    assert get_response.status_code == 200
    assert get_response.json()["blueprint"]["name"] == "sample-lab"

    delete_response = client.delete(f"/blueprints/{blueprint_id}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/blueprints/{blueprint_id}")
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"]["code"] == "NOT_FOUND"


def test_list_blueprints_supports_name_filter_and_pagination():
    first = _valid_payload()
    first["name"] = "lab-a"
    second = _valid_payload()
    second["name"] = "lab-b"
    third = _valid_payload()
    third["name"] = "lab-c"

    assert client.post("/blueprints", json=first).status_code == 200
    assert client.post("/blueprints", json=second).status_code == 200
    assert client.post("/blueprints", json=third).status_code == 200

    filtered = client.get("/blueprints", params={"name": "lab-b"})
    assert filtered.status_code == 200
    filtered_items = filtered.json()
    assert len(filtered_items) == 1
    assert filtered_items[0]["name"] == "lab-b"

    paginated = client.get("/blueprints", params={"limit": 2, "offset": 1})
    assert paginated.status_code == 200
    assert len(paginated.json()) == 2

def test_validate_blueprint_unknown_network_returns_400():
    payload = {
        "name": "invalid-lab",
        "networks": [{"name": "corp-net"}],
        "nodes": [{"name": "ws01", "networks": ["missing-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNKNOWN_NETWORK_REFERENCE"


def test_validate_blueprint_invalid_cidr():
    payload = {
        "name": "invalid-cidr-lab",
        "networks": [{"name": "corp-net", "cidr": "10.10.999.0/24"}],
        "nodes": [{"name": "ws01", "networks": ["corp-net"]}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_CIDR"


def test_validate_blueprint_node_without_network():
    payload = {
        "name": "orphan-node-lab",
        "networks": [{"name": "corp-net"}],
        "nodes": [{"name": "ws01", "networks": []}],
    }

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "NODE_WITHOUT_NETWORK"


def test_validate_blueprint_schema_version_not_supported():
    payload = _valid_payload()
    payload["schema_version"] = "2.0"

    response = client.post("/blueprints/validate", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNSUPPORTED_BLUEPRINT_SCHEMA"
