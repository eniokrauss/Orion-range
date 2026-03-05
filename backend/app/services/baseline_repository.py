from app.db.session import SessionLocal
from app.models.baseline import BaselineRecord


class BaselineNotFoundError(Exception):
    pass


class BaselineRepository:
    def upsert_snapshot(self, blueprint_id: str, snapshot_ref: str) -> BaselineRecord:
        with SessionLocal() as session:
            record = session.get(BaselineRecord, blueprint_id)
            if record is None:
                record = BaselineRecord(
                    blueprint_id=blueprint_id,
                    snapshot_ref=snapshot_ref,
                    reset_count=0,
                )
                session.add(record)
            else:
                record.snapshot_ref = snapshot_ref
                record.reset_count = 0
            session.commit()
            session.refresh(record)
            return record

    def get(self, blueprint_id: str) -> BaselineRecord:
        with SessionLocal() as session:
            record = session.get(BaselineRecord, blueprint_id)
            if record is None:
                raise BaselineNotFoundError(f"Baseline for blueprint '{blueprint_id}' was not found")
            return record

    def mark_reset(self, blueprint_id: str) -> BaselineRecord:
        with SessionLocal() as session:
            record = session.get(BaselineRecord, blueprint_id)
            if record is None:
                raise BaselineNotFoundError(f"Baseline for blueprint '{blueprint_id}' was not found")
            record.reset_count += 1
            session.commit()
            session.refresh(record)
            return record

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(BaselineRecord).delete()
            session.commit()


baseline_repository = BaselineRepository()
