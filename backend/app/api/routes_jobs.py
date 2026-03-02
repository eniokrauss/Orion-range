from fastapi import APIRouter

from app.core.errors import ErrorCode, http_error
from app.schemas.job import CreateJobRequest
from app.services.job_repository import JobNotFoundError, job_repository
from app.services.job_runner import enqueue_job

router = APIRouter(prefix="/jobs")


@router.post("")
def create_job(payload: CreateJobRequest):
    job = job_repository.create(
        action=payload.action,
        target_blueprint_id=payload.target_blueprint_id,
        max_attempts=payload.max_attempts,
    )
    enqueue_job(job.id)

    return {
        "id": job.id,
        "action": job.action,
        "status": job.status,
        "target_blueprint_id": job.target_blueprint_id,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "last_error": job.last_error,
    }


@router.get("")
def list_jobs():
    jobs = job_repository.list()
    return [
        {
            "id": job.id,
            "action": job.action,
            "status": job.status,
            "target_blueprint_id": job.target_blueprint_id,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "last_error": job.last_error,
        }
        for job in jobs
    ]


@router.get("/{job_id}")
def get_job(job_id: str):
    try:
        job = job_repository.get(job_id)
    except JobNotFoundError as exc:
        raise http_error(status_code=404, code=ErrorCode.NOT_FOUND, message=str(exc)) from exc

    return {
        "id": job.id,
        "action": job.action,
        "status": job.status,
        "target_blueprint_id": job.target_blueprint_id,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "last_error": job.last_error,
    }
