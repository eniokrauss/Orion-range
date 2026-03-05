"""
JobStep — persists the state of each individual step within a Job's DAG.

One row per step per job. The job runner writes a row before executing
each step and updates it on completion or failure. On retry/recovery,
steps in state "done" are skipped entirely — this is what gives us
idempotent, checkpoint-based recovery.

Step lifecycle:
  pending → running → done
                   └→ failed
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time_utils import utcnow
from app.db.base import Base


class JobStepRecord(Base):
    __tablename__ = "job_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
