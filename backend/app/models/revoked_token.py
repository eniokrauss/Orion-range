"""
Revoked token registry (by JWT jti).

Used to invalidate refresh tokens after first use (token rotation) and
optionally support explicit token revocation flows.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time_utils import utcnow
from app.db.base import Base


class RevokedTokenRecord(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
