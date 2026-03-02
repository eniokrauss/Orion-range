from app.core.config import settings
from app.services.hypervisors.base import HypervisorAdapter
from app.services.hypervisors.proxmox import ProxmoxAdapter


class HypervisorProviderError(Exception):
    pass


def get_hypervisor_adapter() -> HypervisorAdapter:
    if settings.hypervisor_provider == "proxmox":
        return ProxmoxAdapter()

    raise HypervisorProviderError(f"Unsupported hypervisor provider: {settings.hypervisor_provider}")
