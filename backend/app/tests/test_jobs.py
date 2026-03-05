"""
Integration tests for the /jobs API endpoint and job lifecycle.

These tests run the full stack (FastAPI + SQLite + real job runner in dry-run mode)
to verify end-to-end behavior including the new teardown action and step endpoint.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.baseline_repository import baseline_repository
from app.services.blueprint_repository import blueprint_repository
from app.services.job_repository import job_repository
from app.services.job_step_repository import job_step_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repositories():
    job_step_repository.clear_all()
    job_repository.clear_all()
    baseline_repository.clear_all()
    blueprint_repository.clear_all()
    yield
    job_step_repository.clear_all()
    job_repository.clear_all()
    baseline_repository.clear_all()
    blueprint_repository.clear_all()


def _wait_for_terminal(job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/jobs/{job_id}")
        if r.status_code == 200 and r.json()["status"] in {"succeeded", "failed"}:
            return r.json()
        time.sleep(0.05)
    return client.get(f"/jobs/{job_id}").json()


def _create_blueprint() -> str:
    payload = {
        "name": "job-lab",
        "version": "0.1.0",
        "networks": [{"name": "corp-net", "cidr": "10.0.0.0/24"}],
        "nodes": [{"name": "node-1", "networks": ["corp-net"]}],
    }
    r = client.post("/blueprints", json=payload)
    assert r.status_code == 200
    return r.json()["id"]


# ── basic lifecycle ───────────────────────────────────────────────────────────

def test_provision_job_succeeds():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
    assert r.status_code == 200
    assert _wait_for_terminal(r.json()["id"])["status"] == "succeeded"


def test_snapshot_and_reset_repeatability():
    bp_id = _create_blueprint()

    snap = client.post("/jobs", json={"action": "snapshot", "target_blueprint_id": bp_id, "max_attempts": 1})
    assert _wait_for_terminal(snap.json()["id"])["status"] == "succeeded"

    for _ in range(2):
        reset = client.post("/jobs", json={"action": "reset", "target_blueprint_id": bp_id, "max_attempts": 1})
        assert _wait_for_terminal(reset.json()["id"])["status"] == "succeeded"


def test_teardown_job_succeeds():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "teardown", "target_blueprint_id": bp_id, "max_attempts": 1})
    assert r.status_code == 200
    assert _wait_for_terminal(r.json()["id"])["status"] == "succeeded"


def test_reset_without_baseline_fails():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "reset", "target_blueprint_id": bp_id, "max_attempts": 1})
    result = _wait_for_terminal(r.json()["id"])
    assert result["status"] == "failed"
    assert "Baseline for blueprint" in result["last_error"]


def test_invalid_action_fails():
    r = client.post("/jobs", json={"action": "bad-action", "max_attempts": 1})
    assert _wait_for_terminal(r.json()["id"])["status"] == "failed"
    assert "Unsupported" in client.get(f"/jobs/{r.json()['id']}").json()["last_error"]


def test_missing_blueprint_fails():
    r = client.post("/jobs", json={"action": "snapshot", "target_blueprint_id": "no-such-id", "max_attempts": 1})
    assert _wait_for_terminal(r.json()["id"])["status"] == "failed"
    assert "was not found" in client.get(f"/jobs/{r.json()['id']}").json()["last_error"]


# ── step endpoint ─────────────────────────────────────────────────────────────

def test_job_steps_endpoint_returns_steps():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
    job_id = r.json()["id"]
    _wait_for_terminal(job_id)

    steps_r = client.get(f"/jobs/{job_id}/steps")
    assert steps_r.status_code == 200
    steps = steps_r.json()
    assert len(steps) >= 1
    step_keys = {s["step_key"] for s in steps}
    assert "validate_blueprint" in step_keys
    assert "provision_vms" in step_keys


def test_job_steps_all_done_on_success():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
    job_id = r.json()["id"]
    _wait_for_terminal(job_id)

    steps = client.get(f"/jobs/{job_id}/steps").json()
    assert all(s["status"] == "done" for s in steps), \
        f"Expected all steps done, got: {[(s['step_key'], s['status']) for s in steps]}"


def test_job_steps_missing_job_returns_404():
    r = client.get("/jobs/nonexistent-id/steps")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


# ── list / filter / pagination ────────────────────────────────────────────────

def test_list_jobs_filter_by_action():
    bp_id = _create_blueprint()
    for action in ["provision", "teardown"]:
        r = client.post("/jobs", json={"action": action, "target_blueprint_id": bp_id, "max_attempts": 1})
        _wait_for_terminal(r.json()["id"])

    r = client.get("/jobs", params={"action": "provision"})
    assert r.status_code == 200
    assert all(j["action"] == "provision" for j in r.json())


def test_list_jobs_pagination():
    bp_id = _create_blueprint()
    for _ in range(3):
        r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
        _wait_for_terminal(r.json()["id"])

    r = client.get("/jobs", params={"limit": 2, "offset": 1})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_missing_job_returns_404():
    r = client.get("/jobs/nonexistent")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


# ── response shape ────────────────────────────────────────────────────────────

def test_job_response_includes_timestamps():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
    body = r.json()
    assert "created_at" in body
    assert "updated_at" in body
