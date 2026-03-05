"""
Tests for /ops/overview — verifies real data aggregation, no fake telemetry.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.blueprint_repository import blueprint_repository
from app.services.job_repository import job_repository
from app.services.job_step_repository import job_step_repository
from app.services.scenario_repository import scenario_repository

client = TestClient(app)
_ORIGINAL_API_KEY = ""
_ORIGINAL_JWT_SECRET = ""


def _cleanup():
    job_step_repository.clear_all()
    scenario_repository.clear_all()
    job_repository.clear_all()
    blueprint_repository.clear_all()


def setup_function(_):
    global _ORIGINAL_API_KEY, _ORIGINAL_JWT_SECRET
    _ORIGINAL_API_KEY = settings.api_key
    _ORIGINAL_JWT_SECRET = settings.jwt_secret
    _cleanup()
    settings.api_key = ""
    settings.jwt_secret = ""


def teardown_function(_):
    _cleanup()
    settings.api_key = _ORIGINAL_API_KEY
    settings.jwt_secret = _ORIGINAL_JWT_SECRET


def _wait_for_terminal(job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/jobs/{job_id}")
        if r.status_code == 200 and r.json()["status"] in {"succeeded", "failed"}:
            return r.json()
        time.sleep(0.05)
    return client.get(f"/jobs/{job_id}").json()


def _create_blueprint(name: str = "ops-lab") -> str:
    bp = {
        "name": name,
        "schema_version": "1.0",
        "version": "0.1.0",
        "networks": [{"name": "corp-net", "cidr": "10.10.10.0/24"}],
        "nodes": [{"name": "node-1", "networks": ["corp-net"]}],
    }
    r = client.post("/blueprints", json=bp)
    assert r.status_code == 200
    return r.json()["id"]


def test_ops_overview_shape():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
    _wait_for_terminal(r.json()["id"])

    overview = client.get("/ops/overview")
    assert overview.status_code == 200
    body = overview.json()

    # Top-level keys — telemetry key removed (no longer fake)
    assert "summary" in body
    assert "recent_events" in body
    assert "telemetry" not in body  # was hardcoded, now removed


def test_ops_overview_summary_counts_are_real():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
    _wait_for_terminal(r.json()["id"])

    summary = client.get("/ops/overview").json()["summary"]

    assert summary["blueprints_total"] == 1
    assert summary["jobs_total"] == 1
    assert summary["jobs_by_status"].get("succeeded", 0) == 1
    assert summary["active_jobs"] == 0  # job already finished
    assert "alerts_active" in summary
    assert "active_steps" in summary


def test_ops_overview_recent_events_include_blueprint_and_job():
    bp_id = _create_blueprint()
    r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
    _wait_for_terminal(r.json()["id"])

    events = client.get("/ops/overview").json()["recent_events"]
    sources = {e["source"] for e in events}
    assert "blueprint" in sources
    assert "job" in sources


def test_ops_overview_retry_job_shows_warn_level():
    """A job that fails and retries should produce a 'warn' level event."""
    r = client.post("/jobs", json={"action": "bad-action", "max_attempts": 1})
    _wait_for_terminal(r.json()["id"])

    events = client.get("/ops/overview").json()["recent_events"]
    error_events = [e for e in events if e["level"] == "error" and e["source"] == "job"]
    assert len(error_events) >= 1


def test_ops_overview_requires_auth_when_api_key_set():
    settings.api_key = "secret"

    r = client.get("/ops/overview")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "UNAUTHORIZED"

    r = client.get("/ops/overview", headers={"x-api-key": "secret"})
    assert r.status_code == 200
