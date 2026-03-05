from __future__ import annotations

from app.db.session import SessionLocal
from app.models.user_token_state import UserTokenStateRecord


class UserTokenStateRepository:
    def _get_or_create(self, user_id: str) -> UserTokenStateRecord:
        with SessionLocal() as session:
            record = session.get(UserTokenStateRecord, user_id)
            if record is None:
                record = UserTokenStateRecord(user_id=user_id, token_version=0)
                session.add(record)
                session.commit()
                session.refresh(record)
            return record

    def get_token_version(self, user_id: str) -> int:
        with SessionLocal() as session:
            record = session.get(UserTokenStateRecord, user_id)
            return record.token_version if record is not None else 0

    def bump_token_version(self, user_id: str) -> int:
        with SessionLocal() as session:
            record = session.get(UserTokenStateRecord, user_id)
            if record is None:
                record = UserTokenStateRecord(user_id=user_id, token_version=1)
                session.add(record)
            else:
                record.token_version += 1
            session.commit()
            session.refresh(record)
            return record.token_version

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(UserTokenStateRecord).delete()
            session.commit()


user_token_state_repository = UserTokenStateRepository()
