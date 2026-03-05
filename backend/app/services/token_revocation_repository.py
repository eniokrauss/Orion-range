from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.time_utils import utcnow
from app.db.session import SessionLocal
from app.models.revoked_token import RevokedTokenRecord


class TokenRevocationRepository:
    def is_revoked(self, jti: str) -> bool:
        with SessionLocal() as session:
            record = session.get(RevokedTokenRecord, jti)
            return record is not None

    def revoke(
        self,
        *,
        jti: str,
        token_type: str,
        exp_unix: int,
        subject_id: str | None = None,
        org_id: str | None = None,
        reason: str | None = None,
    ) -> bool:
        expires_at = datetime.fromtimestamp(exp_unix, tz=UTC).replace(tzinfo=None)
        with SessionLocal() as session:
            record = RevokedTokenRecord(
                jti=jti,
                token_type=token_type,
                subject_id=subject_id,
                org_id=org_id,
                reason=reason,
                expires_at=expires_at,
            )
            session.add(record)
            try:
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                return False

    def prune_expired(self) -> int:
        with SessionLocal() as session:
            count = (
                session.query(RevokedTokenRecord)
                .filter(RevokedTokenRecord.expires_at < utcnow())
                .delete()
            )
            session.commit()
            return count

    def _subject_query(
        self,
        *,
        subject_id: str,
        token_type: str | None = None,
        reason: str | None = None,
    ):
        query = select(RevokedTokenRecord).where(RevokedTokenRecord.subject_id == subject_id)
        if token_type:
            query = query.where(RevokedTokenRecord.token_type == token_type)
        if reason:
            query = query.where(RevokedTokenRecord.reason == reason)
        return query

    def count_for_subject(
        self,
        subject_id: str,
        *,
        token_type: str | None = None,
        reason: str | None = None,
    ) -> int:
        with SessionLocal() as session:
            count_query = (
                select(func.count())
                .select_from(RevokedTokenRecord)
                .where(RevokedTokenRecord.subject_id == subject_id)
            )
            if token_type:
                count_query = count_query.where(RevokedTokenRecord.token_type == token_type)
            if reason:
                count_query = count_query.where(RevokedTokenRecord.reason == reason)
            return int(session.execute(count_query).scalar_one())

    def list_for_subject(
        self,
        subject_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        token_type: str | None = None,
        reason: str | None = None,
    ) -> list[RevokedTokenRecord]:
        with SessionLocal() as session:
            query = self._subject_query(subject_id=subject_id, token_type=token_type, reason=reason)
            result = session.execute(
                query
                .order_by(RevokedTokenRecord.revoked_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(RevokedTokenRecord).delete()
            session.commit()


token_revocation_repository = TokenRevocationRepository()
