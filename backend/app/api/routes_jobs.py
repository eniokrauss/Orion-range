from fastapi import APIRouter, Query

from app.core.errors import ErrorCode, http_error
from app.schemas.job import CreateJobRequest
from app.services.job_repository import JobNotFoundError, job_repository
from app.services.job_runner import enqueue_job
from app.services.job_step_repository import job_step_repository

router = APIRouter(prefix="/jobs")


def _job_dict(job) -> dict:
    return {
        "id": job.id,
        "action": job.action,
        "status": job.status,
        "target_blueprint_id": job.target_blueprint_id,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "last_error": job.last_error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.post("")
def create_job(payload: CreateJobRequest):
    job = job_repository.create(
        action=payload.action,
        target_blueprint_id=payload.target_blueprint_id,
        max_attempts=payload.max_attempts,
    )
    enqueue_job(job.id)
    return _job_dict(job)


@router.get("")
def list_jobs(
    status: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    jobs = job_repository.list(status=status, action=action, limit=limit, offset=offset)
    return [_job_dict(j) for j in jobs]


@router.get("/{job_id}")
def get_job(job_id: str):
    try:
        job = job_repository.get(job_id)
    except JobNotFoundError as exc:
        raise http_error(status_code=404, code=ErrorCode.NOT_FOUND, message=str(exc)) from exc
    return _job_dict(job)


@router.get("/{job_id}/steps")
def get_job_steps(job_id: str):
    """
    Return the checkpoint state of every step for this job.

    Useful for debugging partial failures and understanding recovery behavior.
    """
    try:
        job_repository.get(job_id)
    except JobNotFoundError as exc:
        raise http_error(status_code=404, code=ErrorCode.NOT_FOUND, message=str(exc)) from exc

    steps = job_step_repository.list_for_job(job_id)
    return [
        {
            "id": s.id,
            "job_id": s.job_id,
            "step_key": s.step_key,
            "status": s.status,
            "error": s.error,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "created_at": s.created_at.isoformat(),
        }
        for s in steps
    ]
