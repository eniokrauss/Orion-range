from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TechniqueAction:
    technique_id: str
    name: str
    action: str
    description: str
    tactics: tuple[str, ...] = ()


class MitrePlugin(Protocol):
    plugin_name: str

    def resolve(self, technique_id: str) -> TechniqueAction | None:
        ...

    def list_techniques(self) -> list[TechniqueAction]:
        ...
