"""
Garbage collector for orphaned Proxmox resources.

An "orphaned" VM is one whose name starts with the Orion VM prefix
(e.g. "orion-") but whose corresponding blueprint_id no longer exists
in the database — meaning the lab was deleted without a proper teardown,
or a provision job failed mid-way.

The GC runs in two modes:
  dry_run=True  — only reports what would be deleted (safe, default for API)
  dry_run=False — actually deletes the orphaned VMs

The GC is also safe to call with no Proxmox configured (dry-run mode
of the adapter): it will return an empty report.

Scheduling:
  - On-demand via POST /ops/gc
  - Periodic background thread started at app startup (configurable via
    GC_INTERVAL_SECONDS; 0 = disabled)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.log_context import log_context
from app.services.blueprint_repository import blueprint_repository

logger = logging.getLogger(__name__)


@dataclass
class GcReport:
    """Result of one GC run."""
    dry_run: bool
    orphaned_vms: list[str] = field(default_factory=list)
    deleted_vms: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "orphaned_vms": self.orphaned_vms,
            "deleted_vms": self.deleted_vms,
            "errors": self.errors,
            "skipped_reason": self.skipped_reason,
        }


def run_gc(*, dry_run: bool = True) -> GcReport:
    """
    Scan Proxmox for VMs whose names match the Orion prefix but whose
    blueprint_id is not in the database.

    In dry_run mode the report lists orphans but nothing is deleted.
    In non-dry-run mode orphaned VMs are stopped and deleted.

    Returns a GcReport regardless of adapter mode.
    """
    with log_context(gc_dry_run=dry_run):
        logger.info("GC run started (dry_run=%s)", dry_run)
        report = GcReport(dry_run=dry_run)

        # In dry-run adapter mode (no PROXMOX_HOST) there is nothing to scan.
        if not settings.proxmox_host:
            report.skipped_reason = "PROXMOX_HOST not configured — dry-run adapter mode"
            logger.info("GC skipped: %s", report.skipped_reason)
            return report

        try:
            from proxmoxer import ProxmoxAPI  # type: ignore[import]
        except ImportError:
            report.skipped_reason = "proxmoxer not installed"
            logger.warning("GC skipped: %s", report.skipped_reason)
            return report

        # Build client (reuse the same connection logic as the adapter)
        try:
            client = ProxmoxAPI(
                settings.proxmox_host,
                port=settings.proxmox_port,
                user=settings.proxmox_user,
                token_name=settings.proxmox_token_name,
                token_value=settings.proxmox_token_value,
                verify_ssl=settings.proxmox_verify_ssl,
                timeout=30,
            )
        except Exception as exc:
            report.errors.append(f"Connection failed: {exc}")
            logger.error("GC connection error: %s", exc)
            return report

        prefix = settings.proxmox_vm_name_prefix + "-"
        known_ids = _get_known_blueprint_short_ids()

        try:
            vms = client.nodes(settings.proxmox_node).qemu.get()
        except Exception as exc:
            report.errors.append(f"Failed to list VMs: {exc}")
            logger.error("GC list VMs error: %s", exc)
            return report

        for vm in vms:
            name = vm.get("name", "")
            vmid = vm.get("vmid")

            if not name.startswith(prefix):
                continue  # not an Orion VM

            # VM name format: orion-{short_id}-{node_name}
            # Extract the short_id portion (12 chars after prefix)
            remainder = name[len(prefix):]
            short_id = remainder[:12]

            if short_id in known_ids:
                continue  # blueprint still exists — not an orphan

            report.orphaned_vms.append(f"{name} (vmid={vmid})")
            logger.warning("Orphaned VM found: %s vmid=%s", name, vmid)

            if not dry_run:
                try:
                    _delete_vm(client, vmid, name)
                    report.deleted_vms.append(f"{name} (vmid={vmid})")
                    logger.info("Deleted orphaned VM: %s vmid=%s", name, vmid)
                except Exception as exc:
                    msg = f"Failed to delete {name} (vmid={vmid}): {exc}"
                    report.errors.append(msg)
                    logger.error(msg)

        logger.info(
            "GC run complete: orphaned=%d deleted=%d errors=%d",
            len(report.orphaned_vms), len(report.deleted_vms), len(report.errors),
        )
        return report


def _get_known_blueprint_short_ids() -> set[str]:
    """Return the set of blueprint short-IDs (12 hex chars) that are in the DB."""
    blueprints = blueprint_repository.list(limit=10000)
    return {bp.id.replace("-", "")[:12] for bp in blueprints}


def _delete_vm(client, vmid: int, name: str) -> None:
    """Stop and delete a VM. Waits for each task to complete."""
    from app.services.hypervisors.proxmox import _poll_task

    node = settings.proxmox_node

    # Best-effort stop — ignore errors (VM may already be stopped)
    try:
        upid = client.nodes(node).qemu(vmid).status.stop.post()
        _poll_task(client, node, upid,
                   timeout=60, poll_interval=2, operation_label=f"gc-stop:{name}")
    except Exception:
        pass

    upid = client.nodes(node).qemu(vmid).delete(purge=1)
    _poll_task(client, node, upid,
               timeout=120, poll_interval=2, operation_label=f"gc-delete:{name}")


# ── periodic background GC ───────────────────────────────────────────────────

_gc_thread: threading.Thread | None = None
_gc_stop_event = threading.Event()


def start_periodic_gc(interval_seconds: float) -> None:
    """
    Start a background daemon thread that runs the GC every *interval_seconds*.
    interval_seconds=0 disables the periodic GC.
    The GC always runs in dry_run=False mode in the background — it actively
    reclaims orphans. Operators can inspect before enabling via the env var.
    """
    global _gc_thread

    if interval_seconds <= 0:
        logger.info("Periodic GC disabled (GC_INTERVAL_SECONDS=0)")
        return

    if _gc_thread is not None and _gc_thread.is_alive():
        logger.debug("Periodic GC already running")
        return

    _gc_stop_event.clear()

    def _loop():
        logger.info("Periodic GC thread started (interval=%.0fs)", interval_seconds)
        while not _gc_stop_event.wait(timeout=interval_seconds):
            try:
                report = run_gc(dry_run=False)
                if report.orphaned_vms:
                    logger.warning(
                        "Periodic GC: %d orphaned VMs found, %d deleted, %d errors",
                        len(report.orphaned_vms), len(report.deleted_vms), len(report.errors),
                    )
            except Exception as exc:
                logger.error("Periodic GC error: %s", exc)

    _gc_thread = threading.Thread(target=_loop, daemon=True, name="orion-gc")
    _gc_thread.start()


def stop_periodic_gc() -> None:
    """Signal the background GC thread to stop."""
    _gc_stop_event.set()
