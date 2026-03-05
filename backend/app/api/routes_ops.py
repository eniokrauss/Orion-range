"""
Ops routes — overview, GC, and hypervisor health.

GET  /ops/overview       — aggregated runtime stats (jobs, scenarios, blueprints)
GET  /ops/gc             — dry-run scan for orphaned Proxmox VMs (safe, read-only)
POST /ops/gc             — actually delete orphaned VMs (requires range_admin)
GET  /ops/health/hypervisor — hypervisor adapter health check
"""

from fastapi import APIRouter, Depends

from app.core.auth import require_roles
from app.services.gc import run_gc
from app.services.hypervisors.factory import get_hypervisor_adapter
from app.services.ops_overview import get_ops_overview

router = APIRouter(prefix="/ops")


@router.get("/overview")
def ops_overview():
    return get_ops_overview()


@router.get("/gc")
def gc_dry_run():
    """
    Scan Proxmox for orphaned VMs without deleting anything.
    Safe to call at any time — no destructive operations.
    """
    report = run_gc(dry_run=True)
    return report.to_dict()


@router.post("/gc", dependencies=[Depends(require_roles(["range_admin"]))])
def gc_run():
    """
    Find and delete orphaned Proxmox VMs.
    An orphan is a VM whose name starts with the Orion prefix but whose
    blueprint no longer exists in the database.
    Requires range_admin role.
    """
    report = run_gc(dry_run=False)
    return report.to_dict()


@router.get("/health/hypervisor")
def hypervisor_health():
    """
    Return connectivity status of the configured hypervisor adapter.
    In dry-run mode (no PROXMOX_HOST) returns dry_run=True.
    """
    adapter = get_hypervisor_adapter()
    return adapter.health_check()
