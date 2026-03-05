from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NodeSpec:
    """Minimal VM specification derived from a blueprint node."""

    name: str
    vmid: int | None = None              # assigned by provider after creation
    template_vmid: int | None = None     # source template to clone from
    cores: int = 1
    memory_mb: int = 512
    networks: list[str] = field(default_factory=list)


@dataclass
class ProvisionResult:
    """Result returned after a successful provision call."""

    blueprint_id: str
    nodes_created: list[str]             # list of VM names created
    provider_refs: dict[str, int]        # node_name -> vmid


@dataclass
class SnapshotResult:
    """Result returned after a successful snapshot call."""

    blueprint_id: str
    snapshot_ref: str                    # opaque reference stored in baseline


@dataclass
class ResetResult:
    """Result returned after a successful reset call."""

    blueprint_id: str
    snapshot_ref: str
    nodes_restored: list[str]


class HypervisorAdapter(ABC):
    """
    Abstract interface for hypervisor backends.

    All operations are synchronous from the caller's perspective — implementations
    are responsible for polling async tasks internally until completion or timeout.
    """

    @abstractmethod
    def provision(self, blueprint_id: str | None) -> ProvisionResult:
        """
        Create all VMs and networks defined in the blueprint.
        Must be idempotent: if resources already exist they should be left as-is.
        """

    @abstractmethod
    def snapshot(self, blueprint_id: str | None) -> SnapshotResult:
        """
        Take a baseline snapshot of all VMs for this blueprint.
        Returns a SnapshotResult with an opaque snapshot_ref for later restore.
        """

    @abstractmethod
    def reset(self, blueprint_id: str | None) -> ResetResult:
        """
        Restore all VMs to their baseline snapshot.
        Raises ValueError if no baseline exists for the given blueprint_id.
        """

    @abstractmethod
    def teardown(self, blueprint_id: str | None) -> None:
        """
        Destroy all VMs and resources created for this blueprint.
        Must be safe to call even if resources are partially created.
        """

    @abstractmethod
    def health_check(self) -> dict:
        """
        Verify connectivity to the hypervisor and return status info.
        Returns a dict with at least {"connected": bool, "version": str}.
        """
