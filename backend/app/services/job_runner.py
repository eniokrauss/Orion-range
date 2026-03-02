from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Thread
from time import sleep

from app.services.blueprint_repository import BlueprintNotFoundError, blueprint_repository
from app.services.job_repository import job_repository

ALLOWED_ACTIONS = {"provision", "snapshot", "reset"}
ACTION_TIMEOUT_SECONDS = 5


def _execute_action(action: str, target_blueprint_id: str | None) -> None:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported job action '{action}'")

    if target_blueprint_id is not None:
        try:
            blueprint_repository.get(target_blueprint_id)
        except BlueprintNotFoundError as exc:
            raise ValueError(str(exc)) from exc

    sleep(0.1)


def _run_job(job_id: str) -> None:
    job = job_repository.get(job_id)

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
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            status = "failed" if attempt == job.max_attempts else "pending"
            job_repository.update_status(job_id=job_id, status=status, attempts=attempt, last_error=last_error)


def enqueue_job(job_id: str) -> None:
    worker = Thread(target=_run_job, args=(job_id,), daemon=True)
    worker.start()
