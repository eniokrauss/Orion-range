"""
Job runner — checkpoint-based execution of hypervisor jobs.

Every log line emitted during job execution automatically carries:
  job_id, action, blueprint_id, org_id  (set once at job start)
  step_key                               (set per step)

Prometheus metrics are emitted on every terminal state:
  observe_job_completed  — called when job succeeds or permanently fails
  observe_step_completed — called when a step finishes (done or failed)

Step plan per action
--------------------
provision : validate_blueprint → provision_vms
snapshot  : validate_blueprint → create_snapshot
reset     : validate_blueprint → rollback_to_baseline
teardown  : validate_blueprint → destroy_vms
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Lock, Thread
from typing import Callable

from app.core.config import settings
from app.core.log_context import clear_thread_context, set_thread_context
from app.core.observability import metrics_registry
from app.services.blueprint_repository import BlueprintNotFoundError, blueprint_repository
from app.services.hypervisors.factory import HypervisorProviderError, get_hypervisor_adapter
from app.services.job_repository import JobNotFoundError, job_repository
from app.services.job_step_repository import job_step_repository

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = {"provision", "snapshot", "reset", "teardown"}


# ── step plans ────────────────────────────────────────────────────────────────

def _step_plan(action: str, adapter, blueprint_id: str | None) -> list[tuple[str, Callable[[], None]]]:
    if action == "provision":
        return [
            ("validate_blueprint", lambda: _validate_blueprint(blueprint_id)),
            ("provision_vms",      lambda: adapter.provision(blueprint_id)),
        ]
    if action == "snapshot":
        return [
            ("validate_blueprint", lambda: _validate_blueprint(blueprint_id)),
            ("create_snapshot",    lambda: adapter.snapshot(blueprint_id)),
        ]
    if action == "reset":
        return [
            ("validate_blueprint",    lambda: _validate_blueprint(blueprint_id)),
            ("rollback_to_baseline",  lambda: adapter.reset(blueprint_id)),
        ]
    if action == "teardown":
        return [
            ("validate_blueprint", lambda: _validate_blueprint(blueprint_id)),
            ("destroy_vms",        lambda: adapter.teardown(blueprint_id)),
        ]
    raise ValueError(f"Unsupported job action '{action}'")


def _validate_blueprint(blueprint_id: str | None) -> None:
    if blueprint_id is None:
        return
    try:
        blueprint_repository.get(blueprint_id)
    except BlueprintNotFoundError as exc:
        raise ValueError(str(exc)) from exc


def _timeout_for(action: str) -> float:
    return {
        "provision": settings.proxmox_provision_timeout,
        "snapshot":  settings.proxmox_snapshot_timeout,
        "reset":     settings.proxmox_reset_timeout,
        "teardown":  settings.proxmox_provision_timeout,
    }.get(action, 300.0)


# ── dedup guard ───────────────────────────────────────────────────────────────

_running_jobs: set[str] = set()
_running_jobs_lock = Lock()


def _try_mark_job_running(job_id: str) -> bool:
    with _running_jobs_lock:
        if job_id in _running_jobs:
            return False
        _running_jobs.add(job_id)
        return True


def _clear_running_job(job_id: str) -> None:
    with _running_jobs_lock:
        _running_jobs.discard(job_id)


# ── step execution ────────────────────────────────────────────────────────────

def _execute_step_with_timeout(thunk: Callable[[], None], timeout: float, step_key: str) -> None:
    failure: list[Exception] = []

    def _target() -> None:
        try:
            thunk()
        except Exception as exc:  # noqa: BLE001
            failure.append(exc)

    worker = Thread(target=_target, daemon=True, name=f"job-step-{step_key}")
    worker.start()
    worker.join(timeout=timeout)

    if worker.is_alive():
        raise FuturesTimeoutError(f"Step '{step_key}' timed out after {timeout:.0f}s")

    if failure:
        raise failure[0]


def _execute_steps(
    job_id: str,
    action: str,
    steps: list[tuple[str, Callable[[], None]]],
    timeout_per_step: float,
) -> None:
    """
    Execute each step in order, skipping those already marked 'done'.
    Records step-level Prometheus metrics on completion.
    """
    for step_key, thunk in steps:
        job_step_repository.get_or_create(job_id, step_key)

        if job_step_repository.is_done(job_id, step_key):
            logger.debug("Step already done — skipping")
            continue

        set_thread_context(step_key=step_key)
        logger.debug("Step starting")
        job_step_repository.mark_running(job_id, step_key)

        try:
            _execute_step_with_timeout(thunk, timeout_per_step, step_key)
            job_step_repository.mark_done(job_id, step_key)
            metrics_registry.observe_step_completed(action=action, step_key=step_key, status="done")
            logger.debug("Step done")

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            job_step_repository.mark_failed(job_id, step_key, error_msg)
            metrics_registry.observe_step_completed(action=action, step_key=step_key, status="failed")
            logger.warning("Step failed: %s", error_msg)
            raise

        finally:
            set_thread_context(step_key=None)


# ── core job execution ────────────────────────────────────────────────────────

def _run_job(job_id: str) -> None:
    if not _try_mark_job_running(job_id):
        logger.debug("Job %s already running — skipping duplicate enqueue", job_id)
        return

    job_start = time.monotonic()

    try:
        try:
            job = job_repository.get(job_id)
        except JobNotFoundError:
            logger.warning("Job %s not found in DB — aborting", job_id)
            return

        set_thread_context(
            job_id=job_id,
            action=job.action,
            blueprint_id=job.target_blueprint_id,
            org_id=getattr(job, "org_id", None),
        )

        if job.action not in ALLOWED_ACTIONS:
            err = f"Unsupported job action '{job.action}'"
            logger.warning("Invalid action: %s", err)
            _update_job_status_safely(job_id=job_id, status="failed", attempts=1, last_error=err)
            duration = time.monotonic() - job_start
            metrics_registry.observe_job_completed(action=job.action, status="failed", duration_seconds=duration)
            return

        action_timeout = _timeout_for(job.action)
        logger.info(
            "Job starting: action=%r blueprint=%s timeout=%.0fs max_attempts=%d",
            job.action, job.target_blueprint_id, action_timeout, job.max_attempts,
        )

        adapter = get_hypervisor_adapter()
        last_error = ""

        for attempt in range(1, job.max_attempts + 1):
            set_thread_context(attempt=attempt)
            if not _update_job_status_safely(job_id=job_id, status="running", attempts=attempt):
                return
            logger.debug("Attempt %d/%d", attempt, job.max_attempts)

            try:
                steps = _step_plan(job.action, adapter, job.target_blueprint_id)
                _execute_steps(job_id, job.action, steps, action_timeout)

                duration = time.monotonic() - job_start
                if not _update_job_status_safely(job_id=job_id, status="succeeded", attempts=attempt):
                    return
                metrics_registry.observe_job_completed(
                    action=job.action, status="succeeded", duration_seconds=duration
                )
                logger.info("Job succeeded on attempt %d (%.2fs)", attempt, duration)
                return

            except FuturesTimeoutError as exc:
                last_error = str(exc)
                logger.warning("Job timed out on attempt %d: %s", attempt, last_error)

            except (HypervisorProviderError, ValueError, Exception) as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("Job failed on attempt %d: %s", attempt, last_error)

            is_final = attempt == job.max_attempts
            status = "failed" if is_final else "pending"
            if not _update_job_status_safely(
                job_id=job_id,
                status=status,
                attempts=attempt,
                last_error=last_error,
            ):
                return
            if is_final:
                duration = time.monotonic() - job_start
                metrics_registry.observe_job_completed(
                    action=job.action, status="failed", duration_seconds=duration
                )
                logger.error("Job permanently failed after %d attempts (%.2fs)", attempt, duration)

    finally:
        _clear_running_job(job_id)
        clear_thread_context()


def _update_job_status_safely(
    *,
    job_id: str,
    status: str,
    attempts: int,
    last_error: str | None = None,
) -> bool:
    try:
        job_repository.update_status(
            job_id=job_id,
            status=status,
            attempts=attempts,
            last_error=last_error,
        )
    except JobNotFoundError:
        logger.warning("Job %s disappeared before status update to %s", job_id, status)
        return False
    return True


def enqueue_job(job_id: str) -> None:
    """Enqueue a job for background execution. Returns immediately."""
    worker = Thread(target=_run_job, args=(job_id,), daemon=True)
    worker.start()
    logger.debug("Enqueued job %s", job_id)
