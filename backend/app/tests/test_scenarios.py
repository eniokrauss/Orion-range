import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.scenario_repository import scenario_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_runs():
    scenario_repository.clear_all()
    yield
    scenario_repository.clear_all()


def _wait_until_done(run_id: str, timeout_seconds: float = 3.0):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        r = client.get(f"/scenarios/runs/{run_id}")
        if r.status_code == 200 and r.json()["status"] in {"completed", "stopped", "failed"}:
            return r.json()
        time.sleep(0.1)
    return client.get(f"/scenarios/runs/{run_id}").json()


def test_start_scenario_and_complete():
    response = client.post(
        "/scenarios/runs",
        json={
            "scenario_name": "initial-attack",
            "steps": [
                {"name": "inject-phishing", "action": "inject", "delay_ms": 10},
                {"name": "collect-telemetry", "action": "observe", "delay_ms": 10},
            ],
        },
    )
    assert response.status_code == 200
    run_id = response.json()["id"]

    final = _wait_until_done(run_id)
    assert final["status"] == "completed"
    assert len(final["timeline"]) == 2


def test_stop_scenario_run():
    response = client.post(
        "/scenarios/runs",
        json={
            "scenario_name": "long-running",
            "steps": [
                {"name": "step-1", "action": "inject", "delay_ms": 200},
                {"name": "step-2", "action": "observe", "delay_ms": 200},
            ],
        },
    )
    assert response.status_code == 200
    run_id = response.json()["id"]

    stop_response = client.post(f"/scenarios/runs/{run_id}/stop")
    assert stop_response.status_code == 200

    final = _wait_until_done(run_id)
    assert final["status"] in {"stopped", "completed"}


def test_mitre_technique_step_resolves_to_action():
    response = client.post(
        "/scenarios/runs",
        json={
            "scenario_name": "mitre-attack",
            "steps": [
                {"name": "simulate-phishing", "action": "mitre:T1566", "delay_ms": 1},
            ],
        },
    )
    assert response.status_code == 200
    run_id = response.json()["id"]

    final = _wait_until_done(run_id)
    assert final["status"] == "completed"
    assert final["timeline"][0]["action"] == "inject-phishing-email"
    assert final["timeline"][0]["mitre"]["technique_id"] == "T1566"


def test_unknown_mitre_technique_fails_run():
    response = client.post(
        "/scenarios/runs",
        json={
            "scenario_name": "mitre-attack",
            "steps": [
                {"name": "unknown-technique", "action": "mitre:T0000", "delay_ms": 1},
            ],
        },
    )
    assert response.status_code == 200
    run_id = response.json()["id"]

    final = _wait_until_done(run_id)
    assert final["status"] == "failed"
    assert "Unknown MITRE technique" in final["timeline"][0]["error"]


def test_list_scenario_runs_supports_filters_and_pagination():
    first = client.post(
        "/scenarios/runs",
        json={
            "scenario_name": "scenario-a",
            "steps": [{"name": "step-1", "action": "inject", "delay_ms": 1}],
        },
    )
    assert first.status_code == 200
    second = client.post(
        "/scenarios/runs",
        json={
            "scenario_name": "scenario-b",
            "steps": [{"name": "step-1", "action": "mitre:T0000", "delay_ms": 1}],
        },
    )
    assert second.status_code == 200
    third = client.post(
        "/scenarios/runs",
        json={
            "scenario_name": "scenario-c",
            "steps": [{"name": "step-1", "action": "observe", "delay_ms": 1}],
        },
    )
    assert third.status_code == 200

    _wait_until_done(first.json()["id"])
    _wait_until_done(second.json()["id"])
    _wait_until_done(third.json()["id"])

    by_name = client.get("/scenarios/runs", params={"scenario_name": "scenario-b"})
    assert by_name.status_code == 200
    by_name_body = by_name.json()
    assert len(by_name_body) == 1
    assert by_name_body[0]["scenario_name"] == "scenario-b"

    failed_only = client.get("/scenarios/runs", params={"status": "failed"})
    assert failed_only.status_code == 200
    failed_runs = failed_only.json()
    assert len(failed_runs) == 1
    assert failed_runs[0]["status"] == "failed"

    paginated = client.get("/scenarios/runs", params={"limit": 2, "offset": 1})
    assert paginated.status_code == 200
    assert len(paginated.json()) == 2

def test_get_missing_run_returns_standard_error_shape():
    response = client.get("/scenarios/runs/missing-run")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"
