from abc import ABC, abstractmethod


class HypervisorAdapter(ABC):
    @abstractmethod
    def provision(self, blueprint_id: str | None) -> None:
        pass

    @abstractmethod
    def snapshot(self, blueprint_id: str | None) -> None:
        pass

    @abstractmethod
    def reset(self, blueprint_id: str | None) -> None:
        pass
