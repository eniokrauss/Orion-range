from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.blueprint_repository import blueprint_repository
from app.services.job_repository import job_repository
from app.services.scenario_repository import scenario_repository

client = TestClient(app)


def _cleanup():
    scenario_repository.clear_all()
    job_repository.clear_all()
    blueprint_repository.clear_all()


def setup_function(_):
    _cleanup()
    settings.api_key = ""


def teardown_function(_):
    _cleanup()
    settings.api_key = ""


def test_ops_overview_shape():
    bp = {
        "name": "ops-lab",
        "schema_version": "1.0",
        "version": "0.1.0",
        "networks": [{"name": "corp-net", "cidr": "10.10.10.0/24"}],
        "nodes": [{"name": "node-1", "networks": ["corp-net"]}],
    }
    create_bp = client.post("/blueprints", json=bp)
    assert create_bp.status_code == 200

    blueprint_id = create_bp.json()["id"]
    create_job = client.post(
        "/jobs",
        json={"action": "provision", "target_blueprint_id": blueprint_id, "max_attempts": 1},
    )
    assert create_job.status_code == 200

    overview = client.get("/ops/overview")
    assert overview.status_code == 200
    body = overview.json()

    assert "summary" in body
    assert "telemetry" in body
    assert "recent_events" in body
    assert body["summary"]["blueprints_total"] >= 1


def test_ops_overview_requires_auth_when_api_key_set():
    settings.api_key = "secret"

    unauthorized = client.get("/ops/overview")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["detail"]["code"] == "UNAUTHORIZED"

    authorized = client.get("/ops/overview", headers={"x-api-key": "secret"})
    assert authorized.status_code == 200
