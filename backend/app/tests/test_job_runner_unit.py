"""
Unit tests for the job runner and its checkpoint step mechanism.

Uses monkeypatching to isolate the runner from real DB and adapters.
All tests run synchronously via _run_job() — no threading.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from app.services import job_runner


# ── fakes ─────────────────────────────────────────────────────────────────────

class _FakeJobRepository:
    def __init__(self, job):
        self.job = job
        self.updates: list[dict] = []

    def get(self, job_id: str):
        return self.job

    def update_status(self, **kwargs):
        self.updates.append(kwargs)

    def final_status(self) -> str:
        return self.updates[-1]["status"] if self.updates else ""


class _FakeAdapter:
    def __init__(self, fail_on: set[str] | None = None):
        self.calls: list[str] = []
        self._fail_on = fail_on or set()

    def provision(self, _bp_id):
        self.calls.append("provision")
        if "provision" in self._fail_on:
            raise RuntimeError("provision failed")

    def snapshot(self, _bp_id):
        self.calls.append("snapshot")
        if "snapshot" in self._fail_on:
            raise RuntimeError("snapshot failed")

    def reset(self, _bp_id):
        self.calls.append("reset")
        if "reset" in self._fail_on:
            raise RuntimeError("reset failed")

    def teardown(self, _bp_id):
        self.calls.append("teardown")
        if "teardown" in self._fail_on:
            raise RuntimeError("teardown failed")


class _FakeStepRepository:
    """
    In-memory step repository. Tracks step state so the checkpoint
    logic (skip 'done' steps on retry) works correctly in unit tests.
    """

    def __init__(self):
        self._steps: dict[tuple[str, str], str] = {}  # (job_id, step_key) -> status
        self.history: list[tuple[str, str, str]] = []  # (job_id, step_key, action)

    def get_or_create(self, job_id: str, step_key: str):
        key = (job_id, step_key)
        if key not in self._steps:
            self._steps[key] = "pending"
        self.history.append((job_id, step_key, "get_or_create"))
        return SimpleNamespace(job_id=job_id, step_key=step_key, status=self._steps[key])

    def mark_running(self, job_id: str, step_key: str):
        self._steps[(job_id, step_key)] = "running"
        self.history.append((job_id, step_key, "running"))

    def mark_done(self, job_id: str, step_key: str):
        self._steps[(job_id, step_key)] = "done"
        self.history.append((job_id, step_key, "done"))

    def mark_failed(self, job_id: str, step_key: str, error: str):
        self._steps[(job_id, step_key)] = "failed"
        self.history.append((job_id, step_key, f"failed:{error[:30]}"))

    def is_done(self, job_id: str, step_key: str) -> bool:
        return self._steps.get((job_id, step_key)) == "done"

    def list_for_job(self, job_id: str):
        return []

    def clear_for_job(self, job_id: str):
        self._steps = {k: v for k, v in self._steps.items() if k[0] != job_id}

    def clear_all(self):
        self._steps.clear()

    def done_steps(self, job_id: str) -> list[str]:
        return [k[1] for k, v in self._steps.items() if k[0] == job_id and v == "done"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_job(action: str, bp_id: str | None = None, max_attempts: int = 1):
    return SimpleNamespace(
        action=action,
        target_blueprint_id=bp_id,
        max_attempts=max_attempts,
    )


def _patch_all(monkeypatch, job, adapter=None, step_repo=None):
    fake_job_repo = _FakeJobRepository(job)
    fake_adapter = adapter or _FakeAdapter()
    fake_step_repo = step_repo or _FakeStepRepository()

    monkeypatch.setattr(job_runner, "job_repository", fake_job_repo)
    monkeypatch.setattr(job_runner, "get_hypervisor_adapter", lambda: fake_adapter)
    monkeypatch.setattr(job_runner, "job_step_repository", fake_step_repo)
    # Bypass blueprint validation for unit tests
    monkeypatch.setattr(job_runner, "_validate_blueprint", lambda _: None)

    return fake_job_repo, fake_adapter, fake_step_repo


# ── basic execution tests ─────────────────────────────────────────────────────

def test_provision_job_succeeds(monkeypatch):
    job = _make_job("provision", bp_id="bp-1")
    repo, adapter, steps = _patch_all(monkeypatch, job)

    job_runner._run_job("job-1")

    assert repo.final_status() == "succeeded"
    assert "provision" in adapter.calls
    assert "provision_vms" in steps.done_steps("job-1")


def test_snapshot_job_succeeds(monkeypatch):
    job = _make_job("snapshot", bp_id="bp-1")
    repo, adapter, steps = _patch_all(monkeypatch, job)

    job_runner._run_job("job-snap")

    assert repo.final_status() == "succeeded"
    assert "snapshot" in adapter.calls
    assert "create_snapshot" in steps.done_steps("job-snap")


def test_reset_job_succeeds(monkeypatch):
    job = _make_job("reset", bp_id="bp-1")
    repo, adapter, steps = _patch_all(monkeypatch, job)

    job_runner._run_job("job-reset")

    assert repo.final_status() == "succeeded"
    assert "reset" in adapter.calls
    assert "rollback_to_baseline" in steps.done_steps("job-reset")


def test_teardown_job_succeeds(monkeypatch):
    job = _make_job("teardown", bp_id="bp-1")
    repo, adapter, steps = _patch_all(monkeypatch, job)

    job_runner._run_job("job-teardown")

    assert repo.final_status() == "succeeded"
    assert "teardown" in adapter.calls
    assert "destroy_vms" in steps.done_steps("job-teardown")


def test_unsupported_action_fails_immediately(monkeypatch):
    job = _make_job("nuke-everything")
    repo, _, _ = _patch_all(monkeypatch, job)

    job_runner._run_job("job-bad")

    assert repo.final_status() == "failed"
    assert any("Unsupported" in u.get("last_error", "") for u in repo.updates)


# ── deduplication ─────────────────────────────────────────────────────────────

def test_run_job_cleans_running_registry(monkeypatch):
    job = _make_job("provision")
    repo, _, _ = _patch_all(monkeypatch, job)

    job_runner._run_job("job-cleanup")

    assert repo.final_status() == "succeeded"
    assert "job-cleanup" not in job_runner._running_jobs


def test_run_job_ignores_duplicate_execution(monkeypatch):
    job = _make_job("provision")
    repo, _, _ = _patch_all(monkeypatch, job)

    job_id = "job-dup"
    job_runner._running_jobs.add(job_id)
    try:
        job_runner._run_job(job_id)
    finally:
        job_runner._running_jobs.discard(job_id)

    assert repo.updates == []


def test_run_job_handles_missing_job_during_status_update(monkeypatch):
    job = _make_job("provision")
    fake_repo = _FakeJobRepository(job)
    fake_adapter = _FakeAdapter()
    fake_steps = _FakeStepRepository()

    def _missing(*_args, **_kwargs):
        raise job_runner.JobNotFoundError("job disappeared")

    fake_repo.update_status = _missing
    monkeypatch.setattr(job_runner, "job_repository", fake_repo)
    monkeypatch.setattr(job_runner, "get_hypervisor_adapter", lambda: fake_adapter)
    monkeypatch.setattr(job_runner, "job_step_repository", fake_steps)
    monkeypatch.setattr(job_runner, "_validate_blueprint", lambda _: None)

    job_runner._run_job("job-vanished")

    assert "job-vanished" not in job_runner._running_jobs


# ── failure and retry ─────────────────────────────────────────────────────────

def test_job_fails_after_max_attempts(monkeypatch):
    job = _make_job("provision", max_attempts=3)
    adapter = _FakeAdapter(fail_on={"provision"})
    repo, _, _ = _patch_all(monkeypatch, job, adapter=adapter)

    job_runner._run_job("job-fail")

    assert repo.final_status() == "failed"
    # All 3 attempts were made
    running_updates = [u for u in repo.updates if u.get("status") in ("running", "pending", "failed")]
    attempt_numbers = [u["attempts"] for u in running_updates]
    assert max(attempt_numbers) == 3


def test_job_succeeds_after_one_retry(monkeypatch):
    """Adapter fails on first call, succeeds on second."""
    call_count = {"n": 0}

    class _FlakyAdapter(_FakeAdapter):
        def provision(self, bp_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("transient failure")
            super().provision(bp_id)

    job = _make_job("provision", max_attempts=2)
    repo, _, _ = _patch_all(monkeypatch, job, adapter=_FlakyAdapter())

    job_runner._run_job("job-flaky")

    assert repo.final_status() == "succeeded"
    assert call_count["n"] == 2


# ── checkpoint / recovery ─────────────────────────────────────────────────────

def test_done_steps_are_skipped_on_retry(monkeypatch):
    """
    Simulate a recovery scenario: validate_blueprint was already done,
    provision_vms was not. Only provision_vms should be called.
    """
    job = _make_job("provision", bp_id="bp-1")
    adapter = _FakeAdapter()
    step_repo = _FakeStepRepository()
    # Pre-mark validate_blueprint as done (simulates prior partial run)
    step_repo._steps[("job-recover", "validate_blueprint")] = "done"

    _patch_all(monkeypatch, job, adapter=adapter, step_repo=step_repo)

    job_runner._run_job("job-recover")

    # validate_blueprint was pre-done — only provision_vms step ran the thunk
    actions_run = [h[2] for h in step_repo.history if h[0] == "job-recover" and h[2] == "done"]
    assert "done" in actions_run  # provision_vms was marked done

    # The adapter's provision was still called (provision_vms step ran)
    assert "provision" in adapter.calls

    # validate_blueprint was not re-run (step is_done returned True → skipped)
    validate_running = [
        h for h in step_repo.history
        if h[0] == "job-recover" and h[1] == "validate_blueprint" and h[2] == "running"
    ]
    assert validate_running == []


def test_all_steps_recorded_for_provision(monkeypatch):
    """Every step in the provision plan gets a get_or_create call."""
    job = _make_job("provision", bp_id="bp-1")
    _, _, step_repo = _patch_all(monkeypatch, job)

    job_runner._run_job("job-steps")

    created = {h[1] for h in step_repo.history if h[2] == "get_or_create"}
    assert "validate_blueprint" in created
    assert "provision_vms" in created


def test_step_marked_failed_on_adapter_error(monkeypatch):
    job = _make_job("provision", bp_id="bp-1", max_attempts=1)
    adapter = _FakeAdapter(fail_on={"provision"})
    _, _, step_repo = _patch_all(monkeypatch, job, adapter=adapter)

    job_runner._run_job("job-step-fail")

    failed = [h for h in step_repo.history if h[0] == "job-step-fail" and "failed:" in h[2]]
    assert len(failed) >= 1
    assert "provision_vms" in [h[1] for h in failed]


def test_step_timeout_returns_quickly():
    start = time.monotonic()

    with pytest.raises(job_runner.FuturesTimeoutError):
        job_runner._execute_step_with_timeout(
            thunk=lambda: time.sleep(0.3),
            timeout=0.01,
            step_key="slow-step",
        )

    elapsed = time.monotonic() - start
    assert elapsed < 0.15
