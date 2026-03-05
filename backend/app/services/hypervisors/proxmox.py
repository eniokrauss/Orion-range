"""
ProxmoxAdapter — real implementation using proxmoxer.

Design decisions:
- All Proxmox operations are asynchronous (they return a task UPID).
  This adapter polls the task status until it completes or times out.
- VM names follow the pattern: orion-{blueprint_id_short}-{node_name}
  so the garbage collector can identify and reclaim orphaned resources.
- If PROXMOX_HOST is not configured the adapter operates in dry-run mode
  and logs every call without touching any real infrastructure.
  This keeps the test suite and local dev environment functional.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.core.config import settings
from app.services.baseline_repository import BaselineNotFoundError, baseline_repository
from app.services.blueprint_repository import BlueprintNotFoundError, blueprint_repository
from app.services.hypervisors.base import (
    HypervisorAdapter,
    NodeSpec,
    ProvisionResult,
    ResetResult,
    SnapshotResult,
)

logger = logging.getLogger(__name__)

# Snapshot name used for the baseline — fixed so restore is deterministic.
_BASELINE_SNAPSHOT_NAME = "orion-baseline"


# ── helpers ───────────────────────────────────────────────────────────────────

def _vm_name(blueprint_id: str, node_name: str) -> str:
    """Deterministic VM name that encodes enough context for GC."""
    short_id = blueprint_id.replace("-", "")[:12]
    return f"{settings.proxmox_vm_name_prefix}-{short_id}-{node_name}"


def _snapshot_ref(blueprint_id: str) -> str:
    """Opaque reference stored in the baseline record."""
    return json.dumps({
        "blueprint_id": blueprint_id,
        "snapshot_name": _BASELINE_SNAPSHOT_NAME,
    })


def _parse_snapshot_ref(ref: str) -> dict:
    try:
        return json.loads(ref)
    except (json.JSONDecodeError, TypeError):
        return {"snapshot_name": _BASELINE_SNAPSHOT_NAME}


# ── connection factory ────────────────────────────────────────────────────────

def _build_proxmox_client():
    """
    Build and return a proxmoxer ProxmoxAPI client.

    Returns None if PROXMOX_HOST is not configured (dry-run mode).
    Raises ImportError if proxmoxer is not installed.
    Raises ProxmoxConnectionError on authentication failure.
    """
    if not settings.proxmox_host:
        return None

    try:
        from proxmoxer import ProxmoxAPI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "proxmoxer is required for Proxmox integration. "
            "Install it with: pip install proxmoxer requests"
        ) from exc

    if not settings.proxmox_token_name or not settings.proxmox_token_value:
        raise ProxmoxConnectionError(
            "PROXMOX_TOKEN_NAME and PROXMOX_TOKEN_VALUE must be set. "
            "Create an API token in Proxmox: Datacenter > Permissions > API Tokens."
        )

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
        # Verify connectivity with a lightweight call.
        client.version.get()
        return client
    except Exception as exc:
        raise ProxmoxConnectionError(f"Failed to connect to Proxmox at {settings.proxmox_host}: {exc}") from exc


# ── exceptions ────────────────────────────────────────────────────────────────

class ProxmoxConnectionError(Exception):
    """Raised when the adapter cannot establish a connection to Proxmox."""


class ProxmoxTaskError(Exception):
    """Raised when a Proxmox async task finishes with a non-OK status."""


class ProxmoxTaskTimeout(Exception):
    """Raised when polling a Proxmox task exceeds the configured timeout."""


# ── task polling ─────────────────────────────────────────────────────────────

def _poll_task(
    client: Any,
    node: str,
    upid: str,
    *,
    timeout: float,
    poll_interval: float,
    operation_label: str,
) -> None:
    """
    Block until the Proxmox task identified by *upid* completes.

    Raises:
        ProxmoxTaskTimeout — if the task does not finish within *timeout* seconds.
        ProxmoxTaskError   — if the task finishes with a non-OK exit status.
    """
    deadline = time.monotonic() + timeout
    logger.debug("Polling task %s (node=%s, op=%s, timeout=%.0fs)", upid, node, operation_label, timeout)

    while time.monotonic() < deadline:
        try:
            status = client.nodes(node).tasks(upid).status.get()
        except Exception as exc:  # network hiccup — keep polling
            logger.warning("Task poll error (will retry): %s", exc)
            time.sleep(poll_interval)
            continue

        task_status = status.get("status", "")
        exit_status = status.get("exitstatus", "")

        if task_status == "stopped":
            if exit_status == "OK":
                logger.debug("Task %s completed OK", upid)
                return
            raise ProxmoxTaskError(
                f"Proxmox task {upid!r} ({operation_label}) failed with exit status {exit_status!r}"
            )

        time.sleep(poll_interval)

    raise ProxmoxTaskTimeout(
        f"Proxmox task {upid!r} ({operation_label}) did not complete within {timeout:.0f}s"
    )


# ── adapter ───────────────────────────────────────────────────────────────────

class ProxmoxAdapter(HypervisorAdapter):
    """
    Proxmox VE hypervisor adapter.

    When PROXMOX_HOST is not set the adapter runs in DRY-RUN mode:
    all operations are logged and simulated locally so the rest of the
    system (job runner, tests, local dev) continues to function correctly.
    """

    def __init__(self) -> None:
        self._dry_run = not bool(settings.proxmox_host)
        if self._dry_run:
            logger.info(
                "ProxmoxAdapter: PROXMOX_HOST not configured — running in DRY-RUN mode. "
                "No real infrastructure will be modified."
            )
        self._client = None  # lazy-initialised on first real call

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get_client(self) -> Any:
        if self._dry_run:
            return None
        if self._client is None:
            self._client = _build_proxmox_client()
        return self._client

    def _poll(self, node: str, upid: str, *, timeout: float, label: str) -> None:
        _poll_task(
            self._get_client(),
            node,
            upid,
            timeout=timeout,
            poll_interval=settings.proxmox_task_poll_interval,
            operation_label=label,
        )

    def _resolve_blueprint_nodes(self, blueprint_id: str) -> list[NodeSpec]:
        """Fetch blueprint from DB and convert nodes to NodeSpec list."""
        try:
            record = blueprint_repository.get(blueprint_id)
        except BlueprintNotFoundError as exc:
            raise ValueError(str(exc)) from exc

        payload = record.payload
        nodes = payload.get("nodes", [])
        specs: list[NodeSpec] = []
        for node in nodes:
            template_vmid = node.get("proxmox_template_vmid") or settings.proxmox_default_template_vmid
            specs.append(NodeSpec(
                name=node["name"],
                template_vmid=template_vmid,
                networks=node.get("networks", []),
            ))
        return specs

    def _vm_exists(self, vmid: int) -> bool:
        """Return True if a VM with this VMID exists on the configured node."""
        client = self._get_client()
        try:
            client.nodes(settings.proxmox_node).qemu(vmid).status.current.get()
            return True
        except Exception:
            return False

    def _find_vm_by_name(self, name: str) -> int | None:
        """Return the VMID of a VM with the given name, or None if not found."""
        client = self._get_client()
        try:
            vms = client.nodes(settings.proxmox_node).qemu.get()
            for vm in vms:
                if vm.get("name") == name:
                    return int(vm["vmid"])
        except Exception as exc:
            logger.warning("Could not list VMs to find %r: %s", name, exc)
        return None

    def _next_free_vmid(self) -> int:
        """Ask Proxmox for the next available VMID."""
        client = self._get_client()
        return int(client.cluster.nextid.get())

    def _clone_vm(self, template_vmid: int, new_vmid: int, name: str) -> None:
        """Clone a template VM and wait for the task to complete."""
        client = self._get_client()
        logger.info(
            "Cloning template vmid=%d -> vmid=%d name=%r (node=%s)",
            template_vmid, new_vmid, name, settings.proxmox_node,
        )
        upid = client.nodes(settings.proxmox_node).qemu(template_vmid).clone.post(
            newid=new_vmid,
            name=name,
            full=1,
            storage=settings.proxmox_storage,
        )
        self._poll(
            settings.proxmox_node, upid,
            timeout=settings.proxmox_task_timeout,
            label=f"clone:{name}",
        )
        logger.info("Clone completed: vmid=%d name=%r", new_vmid, name)

    def _start_vm(self, vmid: int) -> None:
        client = self._get_client()
        logger.info("Starting vmid=%d", vmid)
        upid = client.nodes(settings.proxmox_node).qemu(vmid).status.start.post()
        self._poll(
            settings.proxmox_node, upid,
            timeout=settings.proxmox_task_timeout,
            label=f"start:{vmid}",
        )

    def _stop_vm(self, vmid: int) -> None:
        client = self._get_client()
        logger.info("Stopping vmid=%d", vmid)
        try:
            upid = client.nodes(settings.proxmox_node).qemu(vmid).status.stop.post()
            self._poll(
                settings.proxmox_node, upid,
                timeout=settings.proxmox_task_timeout,
                label=f"stop:{vmid}",
            )
        except Exception as exc:
            logger.warning("Could not stop vmid=%d (may already be stopped): %s", vmid, exc)

    def _create_snapshot(self, vmid: int, snap_name: str) -> None:
        client = self._get_client()
        logger.info("Creating snapshot %r on vmid=%d", snap_name, vmid)
        upid = client.nodes(settings.proxmox_node).qemu(vmid).snapshot.post(
            snapname=snap_name,
            description="Orion Range baseline snapshot",
        )
        self._poll(
            settings.proxmox_node, upid,
            timeout=settings.proxmox_snapshot_timeout,
            label=f"snapshot:{vmid}:{snap_name}",
        )

    def _rollback_snapshot(self, vmid: int, snap_name: str) -> None:
        client = self._get_client()
        logger.info("Rolling back vmid=%d to snapshot %r", vmid, snap_name)
        upid = client.nodes(settings.proxmox_node).qemu(vmid).snapshot(snap_name).rollback.post()
        self._poll(
            settings.proxmox_node, upid,
            timeout=settings.proxmox_reset_timeout,
            label=f"rollback:{vmid}:{snap_name}",
        )

    def _delete_vm(self, vmid: int) -> None:
        client = self._get_client()
        logger.info("Deleting vmid=%d", vmid)
        try:
            self._stop_vm(vmid)
            upid = client.nodes(settings.proxmox_node).qemu(vmid).delete(purge=1)
            self._poll(
                settings.proxmox_node, upid,
                timeout=settings.proxmox_task_timeout,
                label=f"delete:{vmid}",
            )
        except Exception as exc:
            logger.error("Failed to delete vmid=%d: %s", vmid, exc)
            raise

    # ── public interface ──────────────────────────────────────────────────────

    def provision(self, blueprint_id: str | None) -> ProvisionResult:
        """
        Clone a template VM for each node in the blueprint, then start all VMs.

        Idempotent: nodes whose names already exist in Proxmox are skipped.
        """
        if blueprint_id is None:
            raise ValueError("provision requires a target_blueprint_id")

        nodes = self._resolve_blueprint_nodes(blueprint_id)

        if self._dry_run:
            logger.info(
                "[DRY-RUN] provision blueprint_id=%s nodes=%s",
                blueprint_id, [n.name for n in nodes],
            )
            return ProvisionResult(
                blueprint_id=blueprint_id,
                nodes_created=[n.name for n in nodes],
                provider_refs={n.name: 9000 + i for i, n in enumerate(nodes)},
            )

        created: list[str] = []
        provider_refs: dict[str, int] = {}

        for node in nodes:
            vm_name = _vm_name(blueprint_id, node.name)
            existing_vmid = self._find_vm_by_name(vm_name)

            if existing_vmid is not None:
                logger.info("Node %r already exists as vmid=%d — skipping clone", vm_name, existing_vmid)
                provider_refs[node.name] = existing_vmid
                continue

            new_vmid = self._next_free_vmid()
            template = node.template_vmid or settings.proxmox_default_template_vmid

            self._clone_vm(template, new_vmid, vm_name)
            self._start_vm(new_vmid)

            created.append(node.name)
            provider_refs[node.name] = new_vmid
            logger.info("Provisioned node %r as vmid=%d", node.name, new_vmid)

        logger.info(
            "Provision complete for blueprint_id=%s: created=%s skipped=%d",
            blueprint_id, created, len(nodes) - len(created),
        )
        return ProvisionResult(
            blueprint_id=blueprint_id,
            nodes_created=created,
            provider_refs=provider_refs,
        )

    def snapshot(self, blueprint_id: str | None) -> SnapshotResult:
        """
        Stop each VM, take a snapshot named orion-baseline, then restart.

        Overwrites any existing baseline snapshot for this blueprint.
        """
        if blueprint_id is None:
            raise ValueError("snapshot requires a target_blueprint_id")

        nodes = self._resolve_blueprint_nodes(blueprint_id)
        ref = _snapshot_ref(blueprint_id)

        if self._dry_run:
            logger.info("[DRY-RUN] snapshot blueprint_id=%s", blueprint_id)
            baseline_repository.upsert_snapshot(blueprint_id=blueprint_id, snapshot_ref=ref)
            return SnapshotResult(blueprint_id=blueprint_id, snapshot_ref=ref)

        for node in nodes:
            vm_name = _vm_name(blueprint_id, node.name)
            vmid = self._find_vm_by_name(vm_name)
            if vmid is None:
                raise ValueError(
                    f"Cannot snapshot: VM {vm_name!r} not found in Proxmox. "
                    "Run 'provision' before 'snapshot'."
                )

            # Snapshots are live-capable in Proxmox, but stopping gives consistency.
            self._stop_vm(vmid)
            self._create_snapshot(vmid, _BASELINE_SNAPSHOT_NAME)
            self._start_vm(vmid)
            logger.info("Snapshot %r created for node %r (vmid=%d)", _BASELINE_SNAPSHOT_NAME, vm_name, vmid)

        baseline_repository.upsert_snapshot(blueprint_id=blueprint_id, snapshot_ref=ref)
        logger.info("Baseline snapshot registered for blueprint_id=%s", blueprint_id)
        return SnapshotResult(blueprint_id=blueprint_id, snapshot_ref=ref)

    def reset(self, blueprint_id: str | None) -> ResetResult:
        """
        Roll back every VM to the orion-baseline snapshot.

        Raises ValueError if no baseline record exists for this blueprint_id.
        """
        if blueprint_id is None:
            raise ValueError("reset requires a target_blueprint_id")

        try:
            baseline = baseline_repository.get(blueprint_id)
        except BaselineNotFoundError as exc:
            raise ValueError(str(exc)) from exc

        ref_data = _parse_snapshot_ref(baseline.snapshot_ref)
        snap_name = ref_data.get("snapshot_name", _BASELINE_SNAPSHOT_NAME)

        nodes = self._resolve_blueprint_nodes(blueprint_id)
        restored: list[str] = []

        if self._dry_run:
            logger.info("[DRY-RUN] reset blueprint_id=%s snap=%r", blueprint_id, snap_name)
            baseline_repository.mark_reset(blueprint_id)
            return ResetResult(
                blueprint_id=blueprint_id,
                snapshot_ref=baseline.snapshot_ref,
                nodes_restored=[n.name for n in nodes],
            )

        for node in nodes:
            vm_name = _vm_name(blueprint_id, node.name)
            vmid = self._find_vm_by_name(vm_name)
            if vmid is None:
                logger.warning("VM %r not found during reset — skipping", vm_name)
                continue

            self._stop_vm(vmid)
            self._rollback_snapshot(vmid, snap_name)
            self._start_vm(vmid)
            restored.append(node.name)
            logger.info("Restored node %r (vmid=%d) to snapshot %r", vm_name, vmid, snap_name)

        baseline_repository.mark_reset(blueprint_id)
        logger.info(
            "Reset complete for blueprint_id=%s: restored=%s", blueprint_id, restored
        )
        return ResetResult(
            blueprint_id=blueprint_id,
            snapshot_ref=baseline.snapshot_ref,
            nodes_restored=restored,
        )

    def teardown(self, blueprint_id: str | None) -> None:
        """
        Destroy all VMs created for this blueprint.

        Safe to call even if VMs were only partially created.
        """
        if blueprint_id is None:
            raise ValueError("teardown requires a target_blueprint_id")

        nodes = self._resolve_blueprint_nodes(blueprint_id)

        if self._dry_run:
            logger.info("[DRY-RUN] teardown blueprint_id=%s", blueprint_id)
            return

        for node in nodes:
            vm_name = _vm_name(blueprint_id, node.name)
            vmid = self._find_vm_by_name(vm_name)
            if vmid is None:
                logger.info("VM %r not found during teardown — already removed", vm_name)
                continue
            self._delete_vm(vmid)

        logger.info("Teardown complete for blueprint_id=%s", blueprint_id)

    def health_check(self) -> dict:
        """Return connectivity status and Proxmox version info."""
        if self._dry_run:
            return {
                "connected": False,
                "dry_run": True,
                "version": "n/a",
                "node": settings.proxmox_node,
                "message": "PROXMOX_HOST not configured — dry-run mode active",
            }
        try:
            client = self._get_client()
            version_info = client.version.get()
            return {
                "connected": True,
                "dry_run": False,
                "version": version_info.get("version", "unknown"),
                "release": version_info.get("release", "unknown"),
                "node": settings.proxmox_node,
            }
        except Exception as exc:
            return {
                "connected": False,
                "dry_run": False,
                "version": "n/a",
                "node": settings.proxmox_node,
                "error": str(exc),
            }
