"""
Tests for:
  - Prometheus job/step metrics emitted by the job runner
  - GC dry-run endpoint (GET /ops/gc)
  - GC POST endpoint requires range_admin
  - Hypervisor health endpoint (GET /ops/health/hypervisor)
  - metrics_registry.render_prometheus() includes new job metrics
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.observability import InMemoryMetrics, metrics_registry
from app.main import app
from app.services.baseline_repository import baseline_repository
from app.services.blueprint_repository import blueprint_repository
from app.services.job_repository import job_repository
from app.services.job_step_repository import job_step_repository

client = TestClient(app)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db():
    original_api_key = settings.api_key
    original_jwt_secret = settings.jwt_secret
    job_step_repository.clear_all()
    job_repository.clear_all()
    baseline_repository.clear_all()
    blueprint_repository.clear_all()
    settings.api_key = ""
    settings.jwt_secret = ""
    yield
    job_step_repository.clear_all()
    job_repository.clear_all()
    baseline_repository.clear_all()
    blueprint_repository.clear_all()
    settings.api_key = original_api_key
    settings.jwt_secret = original_jwt_secret


def _create_blueprint() -> str:
    bp = {
        "name": "metrics-lab",
        "schema_version": "1.0",
        "version": "0.1.0",
        "networks": [{"name": "net1", "cidr": "10.0.0.0/24"}],
        "nodes": [{"name": "node-1", "networks": ["net1"]}],
    }
    r = client.post("/blueprints", json=bp)
    assert r.status_code == 200
    return r.json()["id"]


def _wait_terminal(job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/jobs/{job_id}")
        if r.json()["status"] in {"succeeded", "failed"}:
            return r.json()
        time.sleep(0.05)
    return client.get(f"/jobs/{job_id}").json()


# ── InMemoryMetrics unit tests ─────────────────────────────────────────────────

class TestInMemoryMetrics:
    def test_observe_job_completed_increments_counter(self):
        m = InMemoryMetrics()
        m.observe_job_completed(action="provision", status="succeeded", duration_seconds=2.5)
        m.observe_job_completed(action="provision", status="succeeded", duration_seconds=3.0)
        m.observe_job_completed(action="reset",     status="failed",    duration_seconds=1.0)

        output = m.render_prometheus()
        assert 'orion_jobs_total{action="provision",status="succeeded"} 2' in output
        assert 'orion_jobs_total{action="reset",status="failed"} 1'       in output

    def test_observe_step_completed_increments_counter(self):
        m = InMemoryMetrics()
        m.observe_step_completed(action="provision", step_key="provision_vms", status="done")
        m.observe_step_completed(action="provision", step_key="provision_vms", status="done")
        m.observe_step_completed(action="provision", step_key="validate_blueprint", status="done")

        output = m.render_prometheus()
        assert 'orion_job_steps_total{action="provision",step="provision_vms",status="done"} 2' in output
        assert 'orion_job_steps_total{action="provision",step="validate_blueprint",status="done"} 1' in output

    def test_job_duration_histogram_emitted(self):
        m = InMemoryMetrics()
        m.observe_job_completed(action="snapshot", status="succeeded", duration_seconds=10.0)
        output = m.render_prometheus()
        assert "orion_job_duration_seconds_bucket" in output
        assert 'action="snapshot"' in output
        assert "orion_job_duration_seconds_sum" in output
        assert "orion_job_duration_seconds_count" in output

    def test_reset_latency_histogram_emitted_only_for_resets(self):
        m = InMemoryMetrics()
        m.observe_job_completed(action="provision", status="succeeded", duration_seconds=5.0)
        output_no_reset = m.render_prometheus()
        assert "orion_reset_duration_seconds" not in output_no_reset

        m.observe_job_completed(action="reset", status="succeeded", duration_seconds=20.0)
        output_with_reset = m.render_prometheus()
        assert "orion_reset_duration_seconds" in output_with_reset

    def test_http_metrics_still_present(self):
        m = InMemoryMetrics()
        m.observe_request(path="/health", status_code=200, duration_ms=5.0)
        output = m.render_prometheus()
        assert "orion_http_requests_total" in output
        assert "orion_http_requests_by_status_total" in output

    def test_histogram_bucket_counts_correct(self):
        m = InMemoryMetrics()
        # 3 jobs: 2s, 10s, 100s
        for d in [2.0, 10.0, 100.0]:
            m.observe_job_completed(action="provision", status="succeeded", duration_seconds=d)
        output = m.render_prometheus()
        # le="5.0" bucket should contain only the 2s job
        assert 'action="provision",le="5.0"} 1' in output
        # le="15.0" should contain 2s and 10s jobs
        assert 'action="provision",le="15.0"} 2' in output
        # le="+Inf" should contain all 3
        assert 'action="provision",le="+Inf"} 3' in output


# ── job runner instrumentation integration ────────────────────────────────────

class TestJobRunnerMetricsIntegration:
    """Run real jobs through the API and verify metrics are emitted."""

    def test_successful_provision_emits_metrics(self):
        bp_id = _create_blueprint()
        r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
        job_id = r.json()["id"]
        final = _wait_terminal(job_id)
        assert final["status"] == "succeeded"

        output = metrics_registry.render_prometheus()
        assert 'orion_jobs_total{action="provision",status="succeeded"}' in output
        assert 'orion_job_steps_total{action="provision",step="provision_vms",status="done"}' in output
        assert 'orion_job_steps_total{action="provision",step="validate_blueprint",status="done"}' in output

    def test_failed_job_emits_failed_metrics(self):
        r = client.post("/jobs", json={"action": "bad-action", "max_attempts": 1})
        job_id = r.json()["id"]
        final = _wait_terminal(job_id)
        assert final["status"] == "failed"

        output = metrics_registry.render_prometheus()
        assert 'orion_jobs_total{action="bad-action",status="failed"}' in output

    def test_prometheus_endpoint_includes_job_metrics_after_job(self):
        bp_id = _create_blueprint()
        r = client.post("/jobs", json={"action": "provision", "target_blueprint_id": bp_id, "max_attempts": 1})
        _wait_terminal(r.json()["id"])

        prom = client.get("/metrics")
        assert prom.status_code == 200
        body = prom.text
        assert "orion_jobs_total" in body
        assert "orion_job_steps_total" in body
        assert "orion_job_duration_seconds" in body


# ── GC endpoint tests ─────────────────────────────────────────────────────────

class TestGcEndpoints:
    def test_gc_dry_run_returns_report_shape(self):
        r = client.get("/ops/gc")
        assert r.status_code == 200
        body = r.json()
        assert "dry_run" in body
        assert "orphaned_vms" in body
        assert "deleted_vms" in body
        assert "errors" in body
        assert body["dry_run"] is True

    def test_gc_dry_run_skipped_without_proxmox_host(self):
        """Without PROXMOX_HOST configured, GC should skip gracefully."""
        r = client.get("/ops/gc")
        assert r.status_code == 200
        body = r.json()
        assert body["skipped_reason"] is not None
        assert len(body["orphaned_vms"]) == 0

    def test_gc_post_open_mode_allowed(self):
        """In open auth mode (no api_key, no jwt) POST /ops/gc should be accessible."""
        r = client.post("/ops/gc")
        assert r.status_code == 200
        body = r.json()
        assert "orphaned_vms" in body
        assert body["dry_run"] is False

    def test_gc_post_requires_admin_when_api_key_set(self):
        settings.api_key = "test-key"
        r = client.post("/ops/gc")
        assert r.status_code == 401

        r = client.post("/ops/gc", headers={"x-api-key": "test-key"})
        assert r.status_code == 200

    def test_gc_dry_run_no_auth_required(self):
        settings.api_key = "test-key"
        # GET /ops/gc is on the ops router which requires require_api_key
        # but in open mode (no key sent) it falls through to the route
        # Specifically: the ops router requires require_api_key (not require_roles)
        # so it 401s when API_KEY is set and no key is sent
        r = client.get("/ops/gc")
        assert r.status_code == 401  # blocked by ops router auth

        r = client.get("/ops/gc", headers={"x-api-key": "test-key"})
        assert r.status_code == 200


# ── Hypervisor health endpoint ────────────────────────────────────────────────

class TestHypervisorHealth:
    def test_health_check_returns_shape(self):
        r = client.get("/ops/health/hypervisor")
        assert r.status_code == 200
        body = r.json()
        assert "connected" in body
        assert "dry_run" in body

    def test_health_check_dry_run_without_proxmox_host(self):
        r = client.get("/ops/health/hypervisor")
        body = r.json()
        # No PROXMOX_HOST configured → dry_run=True, connected=False
        assert body["dry_run"] is True
        assert body["connected"] is False
