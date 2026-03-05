from typing import List

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.blueprint import BlueprintRecord
from app.schemas.blueprint import LabBlueprint


class BlueprintNotFoundError(Exception):
    pass


class BlueprintRepository:
    def create(self, blueprint: LabBlueprint) -> BlueprintRecord:
        with SessionLocal() as session:
            record = BlueprintRecord(
                name=blueprint.name,
                version=blueprint.version,
                payload=blueprint.model_dump(),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def list(
        self,
        *,
        name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BlueprintRecord]:
        with SessionLocal() as session:
            query = select(BlueprintRecord).order_by(BlueprintRecord.created_at.desc())

            if name:
                query = query.where(BlueprintRecord.name == name)

            query = query.limit(limit).offset(offset)
            result = session.execute(query)
            return list(result.scalars().all())

    def get(self, blueprint_id: str) -> BlueprintRecord:
        with SessionLocal() as session:
            record = session.get(BlueprintRecord, blueprint_id)
            if record is None:
                raise BlueprintNotFoundError(f"Blueprint '{blueprint_id}' was not found")
            return record

    def delete(self, blueprint_id: str) -> None:
        with SessionLocal() as session:
            record = session.get(BlueprintRecord, blueprint_id)
            if record is None:
                raise BlueprintNotFoundError(f"Blueprint '{blueprint_id}' was not found")
            session.delete(record)
            session.commit()

    def clear_all(self) -> None:
        with SessionLocal() as session:
            session.query(BlueprintRecord).delete()
            session.commit()


blueprint_repository = BlueprintRepository()
