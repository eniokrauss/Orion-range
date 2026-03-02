import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_create_job_and_complete_successfully():
    blueprint_payload = {
        "name": "job-lab",
        "version": "0.1.0",
        "networks": [{"name": "corp-net", "cidr": "10.0.0.0/24"}],
        "nodes": [{"name": "node-1", "networks": ["corp-net"]}],
    }
    created_blueprint = client.post("/blueprints", json=blueprint_payload)
    blueprint_id = created_blueprint.json()["id"]

    create_job_response = client.post(
        "/jobs",
        json={"action": "provision", "target_blueprint_id": blueprint_id, "max_attempts": 2},
    )
    assert create_job_response.status_code == 200

    job_id = create_job_response.json()["id"]
    final_job = _wait_for_terminal_status(job_id)
    assert final_job["status"] == "succeeded"


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
