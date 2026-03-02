from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BaselineRecord(Base):
    __tablename__ = "baselines"

    blueprint_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    reset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
