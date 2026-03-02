from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.job import JobRecord


class JobNotFoundError(Exception):
    pass


class JobRepository:
    def create(self, action: str, target_blueprint_id: str | None, max_attempts: int) -> JobRecord:
        with SessionLocal() as session:
            record = JobRecord(
                action=action,
                status="pending",
                target_blueprint_id=target_blueprint_id,
                max_attempts=max_attempts,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get(self, job_id: str) -> JobRecord:
        with SessionLocal() as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                raise JobNotFoundError(f"Job '{job_id}' was not found")
            return record

    def list(self) -> list[JobRecord]:
        with SessionLocal() as session:
            result = session.execute(select(JobRecord).order_by(JobRecord.created_at.desc()))
            return list(result.scalars().all())

    def update_status(self, job_id: str, status: str, attempts: int, last_error: str | None = None) -> JobRecord:
        with SessionLocal() as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                raise JobNotFoundError(f"Job '{job_id}' was not found")
            record.status = status
            record.attempts = attempts
            record.last_error = last_error
            session.commit()
            session.refresh(record)
            return record

codex/verify-the-structure-m2jj1r
    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(JobRecord).delete()
            session.commit()

main

job_repository = JobRepository()
