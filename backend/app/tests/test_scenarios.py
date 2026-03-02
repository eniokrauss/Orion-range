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
        if r.status_code == 200 and r.json()["status"] in {"completed", "stopped"}:
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
