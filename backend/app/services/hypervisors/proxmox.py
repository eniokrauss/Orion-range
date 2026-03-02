from app.services.baseline_repository import BaselineNotFoundError, baseline_repository
from app.services.hypervisors.base import HypervisorAdapter


class ProxmoxAdapter(HypervisorAdapter):
    """Initial Proxmox-first adapter with baseline/reset semantics.

    This stub keeps deterministic behavior for reset validation while
    real provider API integration is implemented in later stages.
    """

    def provision(self, blueprint_id: str | None) -> None:
        if blueprint_id is None:
            raise ValueError("Provision action requires target blueprint id")

    def snapshot(self, blueprint_id: str | None) -> None:
        if blueprint_id is None:
            raise ValueError("Snapshot action requires target blueprint id")
        baseline_repository.upsert_snapshot(
            blueprint_id=blueprint_id,
            snapshot_ref=f"baseline-{blueprint_id}",
        )

    def reset(self, blueprint_id: str | None) -> None:
        if blueprint_id is None:
            raise ValueError("Reset action requires target blueprint id")
        try:
            baseline_repository.mark_reset(blueprint_id)
        except BaselineNotFoundError as exc:
            raise ValueError(str(exc)) from exc
