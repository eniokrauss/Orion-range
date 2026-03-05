"""
User model — supports JWT-based auth with role-based access control.

Roles (stored as comma-separated string for simplicity):
  range_admin  — full access: manage providers, users, all orgs
  instructor   — manage labs, blueprints, scenarios within their org
  student      — start/reset/view own labs, submit flags

Every user belongs to exactly one org. The org_id drives all
multi-tenant query isolation.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time_utils import utcnow
from app.db.base import Base

_DEFAULT_ORG = "default"


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, default=_DEFAULT_ORG)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Roles: comma-separated, e.g. "range_admin" or "instructor,student"
    roles: Mapped[str] = mapped_column(String(200), nullable=False, default="student")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def role_set(self) -> set[str]:
        return {r.strip() for r in self.roles.split(",") if r.strip()}
