"""
Per-user JWT session state.

`token_version` is embedded in issued JWTs and checked on every authenticated
request. Bumping this value invalidates all previously issued tokens.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time_utils import utcnow
from app.db.base import Base


class UserTokenStateRecord(Base):
    __tablename__ = "user_token_states"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
