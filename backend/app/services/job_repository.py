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

    def list(
        self,
        *,
        status: str | None = None,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobRecord]:
        with SessionLocal() as session:
            query = select(JobRecord).order_by(JobRecord.created_at.desc())

            if status:
                query = query.where(JobRecord.status == status)
            if action:
                query = query.where(JobRecord.action == action)

            query = query.limit(limit).offset(offset)
            result = session.execute(query)
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

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(JobRecord).delete()
            session.commit()


job_repository = JobRepository()
