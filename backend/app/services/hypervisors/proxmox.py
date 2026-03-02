from app.services.hypervisors.base import HypervisorAdapter


class ProxmoxAdapter(HypervisorAdapter):
    """Initial Proxmox-first adapter stub.

    This implementation is intentionally lightweight and simulates calls.
    Real API integration is planned in the next stage.
    """

    def provision(self, blueprint_id: str | None) -> None:
        _ = blueprint_id

    def snapshot(self, blueprint_id: str | None) -> None:
        _ = blueprint_id

    def reset(self, blueprint_id: str | None) -> None:
        _ = blueprint_id
