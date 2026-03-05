from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Lock, Thread

from app.services.blueprint_repository import BlueprintNotFoundError, blueprint_repository
from app.services.hypervisors.factory import HypervisorProviderError, get_hypervisor_adapter
from app.services.job_repository import JobNotFoundError, job_repository

ALLOWED_ACTIONS = {"provision", "snapshot", "reset"}
ACTION_TIMEOUT_SECONDS = 5

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


def _execute_action(action: str, target_blueprint_id: str | None) -> None:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported job action '{action}'")

    if target_blueprint_id is not None:
        try:
            blueprint_repository.get(target_blueprint_id)
        except BlueprintNotFoundError as exc:
            raise ValueError(str(exc)) from exc

    adapter = get_hypervisor_adapter()
    if action == "provision":
        adapter.provision(target_blueprint_id)
    elif action == "snapshot":
        adapter.snapshot(target_blueprint_id)
    elif action == "reset":
        adapter.reset(target_blueprint_id)


def _run_job(job_id: str) -> None:
    if not _try_mark_job_running(job_id):
        return

    try:
        try:
            job = job_repository.get(job_id)
        except JobNotFoundError:
            return

        for attempt in range(1, job.max_attempts + 1):
            job_repository.update_status(job_id=job_id, status="running", attempts=attempt)

            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_execute_action, job.action, job.target_blueprint_id)
                    future.result(timeout=ACTION_TIMEOUT_SECONDS)
                job_repository.update_status(job_id=job_id, status="succeeded", attempts=attempt)
                return
            except TimeoutError:
                last_error = f"Action timeout after {ACTION_TIMEOUT_SECONDS}s"
                status = "failed" if attempt == job.max_attempts else "pending"
                job_repository.update_status(job_id=job_id, status=status, attempts=attempt, last_error=last_error)
            except (HypervisorProviderError, Exception) as exc:  # noqa: BLE001
                last_error = str(exc)
                status = "failed" if attempt == job.max_attempts else "pending"
                job_repository.update_status(job_id=job_id, status=status, attempts=attempt, last_error=last_error)
    finally:
        _clear_running_job(job_id)


def enqueue_job(job_id: str) -> None:
    worker = Thread(target=_run_job, args=(job_id,), daemon=True)
    worker.start()
