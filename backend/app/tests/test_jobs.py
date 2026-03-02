import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.baseline_repository import baseline_repository
from app.services.blueprint_repository import blueprint_repository
from app.services.job_repository import job_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repositories():
    job_repository.clear_all()
    baseline_repository.clear_all()
    blueprint_repository.clear_all()
    yield
    job_repository.clear_all()
    baseline_repository.clear_all()
    blueprint_repository.clear_all()


def _wait_for_terminal_status(job_id: str, timeout_seconds: float = 3.0):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/jobs/{job_id}")
        if response.status_code == 200:
            status = response.json()["status"]
            if status in {"succeeded", "failed"}:
                return response.json()
        time.sleep(0.1)
    return client.get(f"/jobs/{job_id}").json()


def _create_blueprint() -> str:
    blueprint_payload = {
        "name": "job-lab",
        "version": "0.1.0",
        "networks": [{"name": "corp-net", "cidr": "10.0.0.0/24"}],
        "nodes": [{"name": "node-1", "networks": ["corp-net"]}],
    }
    created_blueprint = client.post("/blueprints", json=blueprint_payload)
    assert created_blueprint.status_code == 200
    return created_blueprint.json()["id"]


def test_create_job_and_complete_successfully():
    blueprint_id = _create_blueprint()

    create_job_response = client.post(
        "/jobs",
        json={"action": "provision", "target_blueprint_id": blueprint_id, "max_attempts": 2},
    )
    assert create_job_response.status_code == 200

    job_id = create_job_response.json()["id"]
    final_job = _wait_for_terminal_status(job_id)
    assert final_job["status"] == "succeeded"


def test_snapshot_and_reset_repeatability():
    blueprint_id = _create_blueprint()

    snapshot_job = client.post(
        "/jobs",
        json={"action": "snapshot", "target_blueprint_id": blueprint_id, "max_attempts": 1},
    )
    assert snapshot_job.status_code == 200
    snapshot_final = _wait_for_terminal_status(snapshot_job.json()["id"])
    assert snapshot_final["status"] == "succeeded"

    first_reset = client.post(
        "/jobs",
        json={"action": "reset", "target_blueprint_id": blueprint_id, "max_attempts": 1},
    )
    assert first_reset.status_code == 200
    first_reset_final = _wait_for_terminal_status(first_reset.json()["id"])
    assert first_reset_final["status"] == "succeeded"

    second_reset = client.post(
        "/jobs",
        json={"action": "reset", "target_blueprint_id": blueprint_id, "max_attempts": 1},
    )
    assert second_reset.status_code == 200
    second_reset_final = _wait_for_terminal_status(second_reset.json()["id"])
    assert second_reset_final["status"] == "succeeded"


def test_reset_without_baseline_fails():
    blueprint_id = _create_blueprint()

    reset_job = client.post(
        "/jobs",
        json={"action": "reset", "target_blueprint_id": blueprint_id, "max_attempts": 1},
    )
    assert reset_job.status_code == 200
    reset_final = _wait_for_terminal_status(reset_job.json()["id"])
    assert reset_final["status"] == "failed"
    assert "Baseline for blueprint" in reset_final["last_error"]


def test_create_job_with_invalid_action_fails():
    create_job_response = client.post(
        "/jobs",
        json={"action": "unsupported-action", "max_attempts": 2},
    )
    assert create_job_response.status_code == 200

    job_id = create_job_response.json()["id"]
    final_job = _wait_for_terminal_status(job_id)
    assert final_job["status"] == "failed"
    assert "Unsupported job action" in final_job["last_error"]


def test_create_job_with_missing_blueprint_fails():
    create_job_response = client.post(
        "/jobs",
        json={"action": "snapshot", "target_blueprint_id": "non-existent", "max_attempts": 1},
    )
    assert create_job_response.status_code == 200

    job_id = create_job_response.json()["id"]
    final_job = _wait_for_terminal_status(job_id)
    assert final_job["status"] == "failed"
    assert "was not found" in final_job["last_error"]


def test_get_missing_job_returns_standard_error_shape():
    response = client.get("/jobs/missing-job")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"
