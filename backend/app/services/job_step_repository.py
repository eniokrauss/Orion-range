"""
Repository for JobStep — read/write checkpoint state for job recovery.

Key invariant: a step with status='done' is never re-executed by the
job runner. This is what makes recovery idempotent: after a crash, the
runner re-reads all steps for the job, skips 'done' ones, and resumes
from the first non-done step.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.time_utils import utcnow
from app.db.session import SessionLocal
from app.models.job_step import JobStepRecord


class JobStepNotFoundError(Exception):
    pass


class JobStepRepository:

    def get_or_create(self, job_id: str, step_key: str) -> JobStepRecord:
        """
        Return the existing step record for (job_id, step_key), or create
        a new one in 'pending' status if it doesn't exist yet.
        """
        with SessionLocal() as session:
            record = session.execute(
                select(JobStepRecord).where(
                    JobStepRecord.job_id == job_id,
                    JobStepRecord.step_key == step_key,
                )
            ).scalar_one_or_none()

            if record is None:
                record = JobStepRecord(
                    job_id=job_id,
                    step_key=step_key,
                    status="pending",
                    created_at=utcnow(),
                )
                session.add(record)
                session.commit()
                session.refresh(record)

            return record

    def mark_running(self, job_id: str, step_key: str) -> JobStepRecord:
        with SessionLocal() as session:
            record = session.execute(
                select(JobStepRecord).where(
                    JobStepRecord.job_id == job_id,
                    JobStepRecord.step_key == step_key,
                )
            ).scalar_one_or_none()

            if record is None:
                raise JobStepNotFoundError(f"Step '{step_key}' for job '{job_id}' not found")

            record.status = "running"
            record.started_at = utcnow()
            session.commit()
            session.refresh(record)
            return record

    def mark_done(self, job_id: str, step_key: str) -> JobStepRecord:
        with SessionLocal() as session:
            record = session.execute(
                select(JobStepRecord).where(
                    JobStepRecord.job_id == job_id,
                    JobStepRecord.step_key == step_key,
                )
            ).scalar_one_or_none()

            if record is None:
                raise JobStepNotFoundError(f"Step '{step_key}' for job '{job_id}' not found")

            record.status = "done"
            record.finished_at = utcnow()
            record.error = None
            session.commit()
            session.refresh(record)
            return record

    def mark_failed(self, job_id: str, step_key: str, error: str) -> JobStepRecord:
        with SessionLocal() as session:
            record = session.execute(
                select(JobStepRecord).where(
                    JobStepRecord.job_id == job_id,
                    JobStepRecord.step_key == step_key,
                )
            ).scalar_one_or_none()

            if record is None:
                raise JobStepNotFoundError(f"Step '{step_key}' for job '{job_id}' not found")

            record.status = "failed"
            record.finished_at = utcnow()
            record.error = error[:2000]  # guard against huge tracebacks
            session.commit()
            session.refresh(record)
            return record

    def is_done(self, job_id: str, step_key: str) -> bool:
        """
        Return True if this step already completed successfully.
        Used by the runner to skip steps on recovery/retry.
        """
        with SessionLocal() as session:
            record = session.execute(
                select(JobStepRecord).where(
                    JobStepRecord.job_id == job_id,
                    JobStepRecord.step_key == step_key,
                )
            ).scalar_one_or_none()
            return record is not None and record.status == "done"

    def list_for_job(self, job_id: str) -> list[JobStepRecord]:
        """Return all steps for a job ordered by creation time."""
        with SessionLocal() as session:
            result = session.execute(
                select(JobStepRecord)
                .where(JobStepRecord.job_id == job_id)
                .order_by(JobStepRecord.created_at)
            )
            return list(result.scalars().all())

    def clear_for_job(self, job_id: str) -> None:
        """Delete all step records for a job. Used in tests."""
        with SessionLocal() as session:
            session.query(JobStepRecord).filter(JobStepRecord.job_id == job_id).delete()
            session.commit()

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(JobStepRecord).delete()
            session.commit()


job_step_repository = JobStepRepository()
