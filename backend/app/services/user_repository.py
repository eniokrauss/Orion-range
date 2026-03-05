"""Repository for User — create, lookup and manage user accounts."""

from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import UserRecord


class UserNotFoundError(Exception):
    pass


class UserEmailConflictError(Exception):
    pass


class UserRepository:

    def create(
        self,
        email: str,
        hashed_password: str,
        roles: str = "student",
        org_id: str = "default",
    ) -> UserRecord:
        with SessionLocal() as session:
            existing = session.execute(
                select(UserRecord).where(UserRecord.email == email)
            ).scalar_one_or_none()
            if existing is not None:
                raise UserEmailConflictError(f"Email '{email}' is already registered.")

            record = UserRecord(
                email=email,
                hashed_password=hashed_password,
                roles=roles,
                org_id=org_id,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get_by_id(self, user_id: str) -> UserRecord:
        with SessionLocal() as session:
            record = session.get(UserRecord, user_id)
            if record is None:
                raise UserNotFoundError(f"User '{user_id}' was not found.")
            return record

    def get_by_email(self, email: str) -> UserRecord:
        with SessionLocal() as session:
            record = session.execute(
                select(UserRecord).where(UserRecord.email == email)
            ).scalar_one_or_none()
            if record is None:
                raise UserNotFoundError(f"User '{email}' was not found.")
            return record

    def list(
        self,
        *,
        org_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UserRecord]:
        with SessionLocal() as session:
            query = select(UserRecord).order_by(UserRecord.created_at.desc())
            if org_id:
                query = query.where(UserRecord.org_id == org_id)
            query = query.limit(limit).offset(offset)
            return list(session.execute(query).scalars().all())

    def set_active(self, user_id: str, *, active: bool) -> UserRecord:
        with SessionLocal() as session:
            record = session.get(UserRecord, user_id)
            if record is None:
                raise UserNotFoundError(f"User '{user_id}' was not found.")
            record.is_active = active
            session.commit()
            session.refresh(record)
            return record

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(UserRecord).delete()
            session.commit()


user_repository = UserRepository()
