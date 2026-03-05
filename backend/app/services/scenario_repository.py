from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.scenario_run import ScenarioRunRecord


class ScenarioRunNotFoundError(Exception):
    pass


class ScenarioRepository:
    def create(self, scenario_name: str, timeline: list[dict]) -> ScenarioRunRecord:
        with SessionLocal() as session:
            record = ScenarioRunRecord(scenario_name=scenario_name, status="pending", timeline=timeline)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def list(
        self,
        *,
        status: str | None = None,
        scenario_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ScenarioRunRecord]:
        with SessionLocal() as session:
            query = select(ScenarioRunRecord).order_by(ScenarioRunRecord.created_at.desc())

            if status:
                query = query.where(ScenarioRunRecord.status == status)
            if scenario_name:
                query = query.where(ScenarioRunRecord.scenario_name == scenario_name)

            query = query.limit(limit).offset(offset)
            result = session.execute(query)
            return list(result.scalars().all())

    def get(self, run_id: str) -> ScenarioRunRecord:
        with SessionLocal() as session:
            record = session.get(ScenarioRunRecord, run_id)
            if record is None:
                raise ScenarioRunNotFoundError(f"Scenario run '{run_id}' was not found")
            return record

    def update(self, run_id: str, status: str, timeline: list[dict]) -> ScenarioRunRecord:
        with SessionLocal() as session:
            record = session.get(ScenarioRunRecord, run_id)
            if record is None:
                raise ScenarioRunNotFoundError(f"Scenario run '{run_id}' was not found")
            record.status = status
            record.timeline = timeline
            session.commit()
            session.refresh(record)
            return record

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(ScenarioRunRecord).delete()
            session.commit()


scenario_repository = ScenarioRepository()
