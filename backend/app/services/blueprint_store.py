from dataclasses import dataclass
from threading import Lock
from typing import Dict, List
from uuid import uuid4

from app.schemas.blueprint import LabBlueprint


class BlueprintNotFoundError(Exception):
    pass


@dataclass
class StoredBlueprint:
    blueprint_id: str
    blueprint: LabBlueprint


class BlueprintStore:
    def __init__(self) -> None:
        self._items: Dict[str, LabBlueprint] = {}
        self._lock = Lock()

    def create(self, blueprint: LabBlueprint) -> StoredBlueprint:
        with self._lock:
            blueprint_id = str(uuid4())
            self._items[blueprint_id] = blueprint
            return StoredBlueprint(blueprint_id=blueprint_id, blueprint=blueprint)

    def list(self) -> List[StoredBlueprint]:
        with self._lock:
            return [
                StoredBlueprint(blueprint_id=blueprint_id, blueprint=blueprint)
                for blueprint_id, blueprint in self._items.items()
            ]

    def get(self, blueprint_id: str) -> StoredBlueprint:
        with self._lock:
            blueprint = self._items.get(blueprint_id)
            if blueprint is None:
                raise BlueprintNotFoundError(f"Blueprint '{blueprint_id}' was not found")
            return StoredBlueprint(blueprint_id=blueprint_id, blueprint=blueprint)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def delete(self, blueprint_id: str) -> None:
        with self._lock:
            if blueprint_id not in self._items:
                raise BlueprintNotFoundError(f"Blueprint '{blueprint_id}' was not found")
            del self._items[blueprint_id]


blueprint_store = BlueprintStore()
