"""
Unit tests for ProxmoxAdapter.

All tests run in dry-run mode (PROXMOX_HOST not set) so no real
infrastructure is required. Real integration tests against a live
Proxmox host are tracked separately and require env vars to be set.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.baseline_repository import baseline_repository
from app.services.blueprint_repository import blueprint_repository
from app.services.hypervisors.proxmox import (
    ProxmoxAdapter,
    ProxmoxConnectionError,
    ProxmoxTaskError,
    ProxmoxTaskTimeout,
    _BASELINE_SNAPSHOT_NAME,
    _build_proxmox_client,
    _poll_task,
    _snapshot_ref,
    _vm_name,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_repositories():
    blueprint_repository.clear_all()
    baseline_repository.clear_all()
    yield
    blueprint_repository.clear_all()
    baseline_repository.clear_all()


def _create_blueprint(name: str = "test-lab") -> str:
    from app.schemas.blueprint import LabBlueprint, NetworkBP, NodeBP
    bp = LabBlueprint(
        name=name,
        schema_version="1.0",
        version="0.1.0",
        networks=[NetworkBP(name="corp-net", cidr="10.0.0.0/24")],
        nodes=[
            NodeBP(name="dc01", role="dc", networks=["corp-net"], proxmox_template_vmid=9000),
            NodeBP(name="ws01", role="workstation", networks=["corp-net"], proxmox_template_vmid=9000),
        ],
    )
    record = blueprint_repository.create(bp)
    return record.id


# ── helper / naming tests ─────────────────────────────────────────────────────

def test_vm_name_format():
    name = _vm_name("abc-def-123-xyz-000", "dc01")
    assert name.startswith("orion-")
    assert "dc01" in name
    assert len(name) < 60  # Proxmox has a name length limit


def test_snapshot_ref_is_valid_json():
    ref = _snapshot_ref("some-blueprint-id")
    data = json.loads(ref)
    assert data["snapshot_name"] == _BASELINE_SNAPSHOT_NAME
    assert data["blueprint_id"] == "some-blueprint-id"


# ── dry-run mode tests ────────────────────────────────────────────────────────

class TestProxmoxAdapterDryRun:
    """All tests use dry-run mode — no PROXMOX_HOST configured."""

    def test_health_check_reports_dry_run(self):
        adapter = ProxmoxAdapter()
        result = adapter.health_check()
        assert result["connected"] is False
        assert result["dry_run"] is True
        assert "message" in result

    def test_provision_dry_run_returns_result(self):
        bp_id = _create_blueprint()
        adapter = ProxmoxAdapter()
        result = adapter.provision(bp_id)
        assert result.blueprint_id == bp_id
        assert len(result.nodes_created) == 2
        assert "dc01" in result.nodes_created
        assert "ws01" in result.nodes_created

    def test_provision_raises_without_blueprint_id(self):
        adapter = ProxmoxAdapter()
        with pytest.raises(ValueError, match="requires a target_blueprint_id"):
            adapter.provision(None)

    def test_provision_raises_for_unknown_blueprint(self):
        adapter = ProxmoxAdapter()
        with pytest.raises(ValueError, match="was not found"):
            adapter.provision("non-existent-id")

    def test_snapshot_dry_run_registers_baseline(self):
        bp_id = _create_blueprint()
        adapter = ProxmoxAdapter()
        result = adapter.snapshot(bp_id)
        assert result.blueprint_id == bp_id
        assert result.snapshot_ref

        # Baseline record must be persisted in DB
        from app.services.baseline_repository import baseline_repository as br
        baseline = br.get(bp_id)
        assert baseline.blueprint_id == bp_id
        assert baseline.reset_count == 0

    def test_snapshot_raises_without_blueprint_id(self):
        adapter = ProxmoxAdapter()
        with pytest.raises(ValueError):
            adapter.snapshot(None)

    def test_reset_dry_run_increments_reset_count(self):
        bp_id = _create_blueprint()
        adapter = ProxmoxAdapter()

        adapter.snapshot(bp_id)  # register baseline first

        result = adapter.reset(bp_id)
        assert result.blueprint_id == bp_id
        assert len(result.nodes_restored) == 2

        from app.services.baseline_repository import baseline_repository as br
        baseline = br.get(bp_id)
        assert baseline.reset_count == 1

        # Second reset increments again
        adapter.reset(bp_id)
        assert br.get(bp_id).reset_count == 2

    def test_reset_fails_without_baseline(self):
        bp_id = _create_blueprint()
        adapter = ProxmoxAdapter()
        with pytest.raises(ValueError, match="Baseline for blueprint"):
            adapter.reset(bp_id)

    def test_reset_raises_without_blueprint_id(self):
        adapter = ProxmoxAdapter()
        with pytest.raises(ValueError):
            adapter.reset(None)

    def test_teardown_dry_run_does_not_raise(self):
        bp_id = _create_blueprint()
        adapter = ProxmoxAdapter()
        # Should complete silently
        adapter.teardown(bp_id)

    def test_teardown_raises_without_blueprint_id(self):
        adapter = ProxmoxAdapter()
        with pytest.raises(ValueError):
            adapter.teardown(None)

    def test_full_lifecycle_dry_run(self):
        """provision → snapshot → reset × 2 → teardown — all in dry-run mode."""
        bp_id = _create_blueprint()
        adapter = ProxmoxAdapter()

        provision_result = adapter.provision(bp_id)
        assert len(provision_result.nodes_created) == 2

        snapshot_result = adapter.snapshot(bp_id)
        assert snapshot_result.snapshot_ref

        reset_result_1 = adapter.reset(bp_id)
        assert len(reset_result_1.nodes_restored) == 2

        reset_result_2 = adapter.reset(bp_id)
        assert len(reset_result_2.nodes_restored) == 2

        from app.services.baseline_repository import baseline_repository as br
        assert br.get(bp_id).reset_count == 2

        adapter.teardown(bp_id)  # must not raise


# ── task polling unit tests ───────────────────────────────────────────────────

class TestPollTask:
    """Unit tests for the _poll_task helper — mocks the client."""

    def _make_client(self, statuses: list[dict]):
        """Build a mock client that returns each status dict in sequence."""
        mock_client = MagicMock()
        status_mock = mock_client.nodes.return_value.tasks.return_value.status.get
        status_mock.side_effect = statuses
        return mock_client

    def test_poll_completes_on_ok(self):
        client = self._make_client([
            {"status": "running"},
            {"status": "stopped", "exitstatus": "OK"},
        ])
        # Should not raise
        _poll_task(client, "pve", "UPID:test", timeout=10, poll_interval=0, operation_label="test")

    def test_poll_raises_on_task_error(self):
        client = self._make_client([
            {"status": "stopped", "exitstatus": "ERROR: disk full"},
        ])
        with pytest.raises(ProxmoxTaskError, match="disk full"):
            _poll_task(client, "pve", "UPID:test", timeout=10, poll_interval=0, operation_label="test")

    def test_poll_raises_on_timeout(self):
        client = self._make_client([
            {"status": "running"},
            {"status": "running"},
            {"status": "running"},
        ])
        with pytest.raises(ProxmoxTaskTimeout):
            # Very short timeout — will expire before task finishes
            _poll_task(client, "pve", "UPID:test", timeout=0.01, poll_interval=0, operation_label="test")

    def test_poll_retries_on_network_hiccup(self):
        """A transient exception during polling should be swallowed and retried."""
        mock_client = MagicMock()
        status_mock = mock_client.nodes.return_value.tasks.return_value.status.get
        status_mock.side_effect = [
            Exception("connection reset"),
            {"status": "stopped", "exitstatus": "OK"},
        ]
        # Should recover and complete without raising
        _poll_task(mock_client, "pve", "UPID:test", timeout=10, poll_interval=0, operation_label="test")


# ── job runner integration (dry-run) ─────────────────────────────────────────

class TestJobRunnerWithProxmox:
    """Verify the job runner correctly dispatches teardown (new action) in dry-run."""

    def test_teardown_job_succeeds_dry_run(self):
        import time
        from fastapi.testclient import TestClient
        from app.main import app
        from app.services.job_repository import job_repository

        client = TestClient(app)
        job_repository.clear_all()

        bp_id = _create_blueprint()

        resp = client.post("/jobs", json={"action": "teardown", "target_blueprint_id": bp_id, "max_attempts": 1})
        assert resp.status_code == 200
        job_id = resp.json()["id"]

        deadline = time.time() + 5.0
        while time.time() < deadline:
            r = client.get(f"/jobs/{job_id}")
            if r.json()["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.1)

        assert client.get(f"/jobs/{job_id}").json()["status"] == "succeeded"
        job_repository.clear_all()


# ── real-mode (mocked client) tests ──────────────────────────────────────────

@pytest.fixture
def proxmox_settings_real_mode():
    original = {
        "proxmox_host": settings.proxmox_host,
        "proxmox_user": settings.proxmox_user,
        "proxmox_port": settings.proxmox_port,
        "proxmox_token_name": settings.proxmox_token_name,
        "proxmox_token_value": settings.proxmox_token_value,
        "proxmox_node": settings.proxmox_node,
        "proxmox_storage": settings.proxmox_storage,
        "proxmox_default_template_vmid": settings.proxmox_default_template_vmid,
        "proxmox_vm_name_prefix": settings.proxmox_vm_name_prefix,
    }

    settings.proxmox_host = "pve.local"
    settings.proxmox_user = "root@pam"
    settings.proxmox_port = 8006
    settings.proxmox_token_name = "orion-token"
    settings.proxmox_token_value = "secret"
    settings.proxmox_node = "pve"
    settings.proxmox_storage = "local-lvm"
    settings.proxmox_default_template_vmid = 9000
    settings.proxmox_vm_name_prefix = "orion"
    try:
        yield
    finally:
        settings.proxmox_host = original["proxmox_host"]
        settings.proxmox_user = original["proxmox_user"]
        settings.proxmox_port = original["proxmox_port"]
        settings.proxmox_token_name = original["proxmox_token_name"]
        settings.proxmox_token_value = original["proxmox_token_value"]
        settings.proxmox_node = original["proxmox_node"]
        settings.proxmox_storage = original["proxmox_storage"]
        settings.proxmox_default_template_vmid = original["proxmox_default_template_vmid"]
        settings.proxmox_vm_name_prefix = original["proxmox_vm_name_prefix"]


class _FakeCloneApi:
    def __init__(self, client, template_vmid: int):
        self._client = client
        self._template_vmid = template_vmid

    def post(self, *, newid: int, name: str, full: int, storage: str) -> str:
        self._client.calls.append(("clone", self._template_vmid, newid, name, storage))
        self._client.vms[newid] = {
            "name": name,
            "state": "stopped",
            "snapshots": set(),
        }
        return f"UPID:clone:{newid}"


class _FakeStatusCurrentApi:
    def __init__(self, client, vmid: int):
        self._client = client
        self._vmid = vmid

    def get(self) -> dict:
        vm = self._client.vms.get(self._vmid)
        if vm is None:
            raise RuntimeError("VM not found")
        return {"status": vm["state"]}


class _FakeStatusActionApi:
    def __init__(self, client, vmid: int, action: str):
        self._client = client
        self._vmid = vmid
        self._action = action

    def post(self) -> str:
        if self._vmid not in self._client.vms:
            raise RuntimeError("VM not found")
        new_state = "running" if self._action == "start" else "stopped"
        self._client.vms[self._vmid]["state"] = new_state
        self._client.calls.append((self._action, self._vmid))
        return f"UPID:{self._action}:{self._vmid}"


class _FakeStatusApi:
    def __init__(self, client, vmid: int):
        self.current = _FakeStatusCurrentApi(client, vmid)
        self.start = _FakeStatusActionApi(client, vmid, "start")
        self.stop = _FakeStatusActionApi(client, vmid, "stop")


class _FakeRollbackApi:
    def __init__(self, client, vmid: int, snap_name: str):
        self._client = client
        self._vmid = vmid
        self._snap_name = snap_name

    def post(self) -> str:
        vm = self._client.vms.get(self._vmid)
        if vm is None:
            raise RuntimeError("VM not found")
        if self._snap_name not in vm["snapshots"]:
            raise RuntimeError(f"snapshot {self._snap_name!r} not found")
        self._client.calls.append(("rollback", self._vmid, self._snap_name))
        return f"UPID:rollback:{self._vmid}:{self._snap_name}"


class _FakeSnapshotApi:
    def __init__(self, client, vmid: int):
        self._client = client
        self._vmid = vmid

    def post(self, *, snapname: str, description: str) -> str:
        vm = self._client.vms.get(self._vmid)
        if vm is None:
            raise RuntimeError("VM not found")
        vm["snapshots"].add(snapname)
        self._client.calls.append(("snapshot", self._vmid, snapname))
        return f"UPID:snapshot:{self._vmid}:{snapname}"

    def __call__(self, snap_name: str) -> SimpleNamespace:
        return SimpleNamespace(rollback=_FakeRollbackApi(self._client, self._vmid, snap_name))


class _FakeVmApi:
    def __init__(self, client, vmid: int):
        self._client = client
        self._vmid = vmid
        self.clone = _FakeCloneApi(client, vmid)
        self.status = _FakeStatusApi(client, vmid)
        self.snapshot = _FakeSnapshotApi(client, vmid)

    def delete(self, purge: int = 1) -> str:
        self._client.calls.append(("delete", self._vmid, purge))
        self._client.vms.pop(self._vmid, None)
        return f"UPID:delete:{self._vmid}"


class _FakeQemuApi:
    def __init__(self, client):
        self._client = client

    def get(self) -> list[dict]:
        return [
            {"vmid": vmid, "name": data["name"]}
            for vmid, data in sorted(self._client.vms.items())
        ]

    def __call__(self, vmid: int) -> _FakeVmApi:
        return _FakeVmApi(self._client, vmid)


class _FakeNodeApi:
    def __init__(self, client):
        self.qemu = _FakeQemuApi(client)


class _FakeClusterApi:
    def __init__(self, client):
        self.nextid = SimpleNamespace(get=client.nextid_get)


class _FakeProxmoxClient:
    def __init__(self):
        self.vms: dict[int, dict] = {}
        self.calls: list[tuple] = []
        self._nextid = 110
        self.cluster = _FakeClusterApi(self)
        self.version = SimpleNamespace(get=lambda: {"version": "8.2.0", "release": "8.2"})

    def nextid_get(self) -> int:
        vmid = self._nextid
        self._nextid += 1
        return vmid

    def nodes(self, _node: str) -> _FakeNodeApi:
        return _FakeNodeApi(self)


class TestBuildProxmoxClient:
    def test_returns_none_without_host(self):
        original_host = settings.proxmox_host
        settings.proxmox_host = ""
        try:
            assert _build_proxmox_client() is None
        finally:
            settings.proxmox_host = original_host

    def test_raises_when_token_is_missing(self, proxmox_settings_real_mode):
        settings.proxmox_token_name = ""
        settings.proxmox_token_value = ""
        with patch.dict("sys.modules", {"proxmoxer": SimpleNamespace(ProxmoxAPI=object)}):
            with pytest.raises(ProxmoxConnectionError, match="PROXMOX_TOKEN_NAME"):
                _build_proxmox_client()

    def test_builds_client_and_checks_version(self, proxmox_settings_real_mode):
        captured: dict = {}

        class _FakeProxmoxApi:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
                self.version = SimpleNamespace(get=lambda: {"version": "8.1.0", "release": "8.1"})

        with patch.dict("sys.modules", {"proxmoxer": SimpleNamespace(ProxmoxAPI=_FakeProxmoxApi)}):
            client = _build_proxmox_client()

        assert client is not None
        assert captured["args"][0] == "pve.local"
        assert captured["kwargs"]["token_name"] == "orion-token"
        assert captured["kwargs"]["token_value"] == "secret"


class TestProxmoxAdapterRealModeMocked:
    def test_provision_creates_missing_nodes_and_skips_existing(self, proxmox_settings_real_mode):
        bp_id = _create_blueprint()
        existing_name = _vm_name(bp_id, "dc01")
        fake_client = _FakeProxmoxClient()
        fake_client.vms[901] = {
            "name": existing_name,
            "state": "running",
            "snapshots": set(),
        }

        with patch("app.services.hypervisors.proxmox._build_proxmox_client", return_value=fake_client):
            adapter = ProxmoxAdapter()
            with patch.object(adapter, "_poll", return_value=None):
                result = adapter.provision(bp_id)

        assert result.blueprint_id == bp_id
        assert result.nodes_created == ["ws01"]
        assert result.provider_refs["dc01"] == 901
        assert result.provider_refs["ws01"] == 110
        assert any(call[0] == "clone" and call[2] == 110 for call in fake_client.calls)
        assert any(call[0] == "start" and call[1] == 110 for call in fake_client.calls)

    def test_snapshot_and_reset_full_lifecycle_in_real_mode(self, proxmox_settings_real_mode):
        bp_id = _create_blueprint()
        fake_client = _FakeProxmoxClient()

        with patch("app.services.hypervisors.proxmox._build_proxmox_client", return_value=fake_client):
            adapter = ProxmoxAdapter()
            with patch.object(adapter, "_poll", return_value=None):
                provision_result = adapter.provision(bp_id)
                snapshot_result = adapter.snapshot(bp_id)
                reset_result = adapter.reset(bp_id)

        assert len(provision_result.nodes_created) == 2
        assert snapshot_result.snapshot_ref
        assert len(reset_result.nodes_restored) == 2
        assert _snapshot_ref(bp_id) == snapshot_result.snapshot_ref

        baseline = baseline_repository.get(bp_id)
        assert baseline.reset_count == 1

        # Every VM provisioned for the blueprint must have the baseline snapshot.
        for vm in fake_client.vms.values():
            assert _BASELINE_SNAPSHOT_NAME in vm["snapshots"]
