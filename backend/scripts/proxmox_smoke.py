#!/usr/bin/env python3
"""
Operational smoke test for Orion Proxmox flow through backend API.

Flow:
  1) Check /ops/health/hypervisor
  2) Create a minimal blueprint
  3) Submit and wait for jobs: provision -> snapshot -> reset
  4) Cleanup: teardown job + blueprint deletion
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests


TERMINAL_JOB_STATUSES = {"succeeded", "failed"}


class SmokeTestError(RuntimeError):
    """Raised when smoke validation fails."""


def _now_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _headers(api_key: str, access_token: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    expected_status: int | None = None,
    **kwargs: Any,
) -> Any:
    response = session.request(method, url, timeout=30, **kwargs)
    if expected_status is not None and response.status_code != expected_status:
        raise SmokeTestError(
            f"{method} {url} returned HTTP {response.status_code}, expected {expected_status}: {response.text[:800]}"
        )
    if expected_status is None and not response.ok:
        raise SmokeTestError(f"{method} {url} returned HTTP {response.status_code}: {response.text[:800]}")
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise SmokeTestError(f"{method} {url} did not return JSON: {response.text[:400]}") from exc


def _create_smoke_blueprint_payload(*, name_prefix: str, template_vmid: int | None) -> dict[str, Any]:
    node: dict[str, Any] = {
        "name": "smoke-node-1",
        "role": "server",
        "networks": ["smoke-net"],
    }
    if template_vmid is not None:
        node["proxmox_template_vmid"] = template_vmid

    return {
        "name": f"{name_prefix}-{_now_suffix()}",
        "schema_version": "1.0",
        "version": "0.1.0",
        "networks": [{"name": "smoke-net", "cidr": "10.66.0.0/24"}],
        "nodes": [node],
    }


def _wait_job_terminal(
    session: requests.Session,
    *,
    base_url: str,
    job_id: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        last = _request_json(session, "GET", urljoin(base_url, f"/jobs/{job_id}"))
        status = last.get("status")
        if status in TERMINAL_JOB_STATUSES:
            return last
        time.sleep(poll_interval_seconds)

    raise SmokeTestError(
        f"Job {job_id} did not finish within {timeout_seconds:.0f}s. Last status: {last.get('status') if last else 'unknown'}"
    )


def _submit_and_wait_job(
    session: requests.Session,
    *,
    base_url: str,
    action: str,
    blueprint_id: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    job = _request_json(
        session,
        "POST",
        urljoin(base_url, "/jobs"),
        json={"action": action, "target_blueprint_id": blueprint_id, "max_attempts": 1},
    )
    job_id = str(job["id"])
    print(f"[smoke] submitted job action={action} id={job_id}")

    final = _wait_job_terminal(
        session,
        base_url=base_url,
        job_id=job_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    print(f"[smoke] job id={job_id} action={action} status={final['status']}")
    return final


def _print_failed_steps(session: requests.Session, *, base_url: str, job_id: str) -> None:
    try:
        steps = _request_json(session, "GET", urljoin(base_url, f"/jobs/{job_id}/steps"))
    except Exception as exc:  # noqa: BLE001
        print(f"[smoke] could not fetch failed steps for job {job_id}: {exc}")
        return

    if not isinstance(steps, list) or not steps:
        print(f"[smoke] no steps returned for failed job {job_id}")
        return

    print(f"[smoke] checkpoint details for failed job {job_id}:")
    for step in steps:
        status = step.get("status", "unknown")
        key = step.get("step_key", "?")
        err = str(step.get("error") or "").strip()
        err_short = (err[:500] + "...") if len(err) > 500 else err
        line = f"  - {key}: {status}"
        if err_short:
            line += f" | error={err_short}"
        print(line)


def run_smoke(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    session.headers.update(_headers(args.api_key, args.access_token))

    blueprint_id: str | None = None
    teardown_job_id: str | None = None

    try:
        health = _request_json(session, "GET", urljoin(base_url, "/ops/health/hypervisor"))
        print(f"[smoke] hypervisor health: {health}")

        connected = bool(health.get("connected"))
        dry_run = bool(health.get("dry_run"))
        if not args.allow_dry_run and (not connected or dry_run):
            raise SmokeTestError(
                "Hypervisor is not connected in real mode. "
                "Set Proxmox env vars on backend or rerun with --allow-dry-run."
            )

        payload = _create_smoke_blueprint_payload(
            name_prefix=args.blueprint_prefix,
            template_vmid=args.template_vmid,
        )
        blueprint = _request_json(session, "POST", urljoin(base_url, "/blueprints"), json=payload)
        blueprint_id = str(blueprint["id"])
        print(f"[smoke] created blueprint id={blueprint_id} name={payload['name']}")

        for action in ("provision", "snapshot", "reset"):
            final = _submit_and_wait_job(
                session,
                base_url=base_url,
                action=action,
                blueprint_id=blueprint_id,
                timeout_seconds=args.job_timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            if final.get("status") != "succeeded":
                _print_failed_steps(session, base_url=base_url, job_id=final["id"])
                raise SmokeTestError(
                    f"Smoke flow failed on action={action}. "
                    f"job_id={final['id']} last_error={final.get('last_error')!r}"
                )

        print("[smoke] SUCCESS: provision -> snapshot -> reset completed.")
        return 0

    finally:
        if blueprint_id and not args.skip_teardown:
            try:
                teardown_final = _submit_and_wait_job(
                    session,
                    base_url=base_url,
                    action="teardown",
                    blueprint_id=blueprint_id,
                    timeout_seconds=args.job_timeout_seconds,
                    poll_interval_seconds=args.poll_interval_seconds,
                )
                teardown_job_id = teardown_final["id"]
                if teardown_final.get("status") != "succeeded":
                    _print_failed_steps(session, base_url=base_url, job_id=teardown_job_id)
                    print(
                        "[smoke] WARN: teardown job did not succeed. "
                        f"job_id={teardown_job_id} last_error={teardown_final.get('last_error')!r}"
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"[smoke] WARN: teardown submission failed: {exc}")

        if blueprint_id and not args.keep_blueprint:
            try:
                _request_json(
                    session,
                    "DELETE",
                    urljoin(base_url, f"/blueprints/{blueprint_id}"),
                    expected_status=204,
                )
                print(f"[smoke] deleted blueprint id={blueprint_id}")
            except Exception as exc:  # noqa: BLE001
                print(f"[smoke] WARN: could not delete blueprint id={blueprint_id}: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Orion Proxmox operational smoke test via backend API.",
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend API base URL.")
    parser.add_argument("--api-key", default="", help="x-api-key value (optional in open mode).")
    parser.add_argument("--access-token", default="", help="JWT bearer access token (optional).")
    parser.add_argument(
        "--template-vmid",
        type=int,
        default=None,
        help="Template VMID to inject in smoke blueprint node.",
    )
    parser.add_argument(
        "--job-timeout-seconds",
        type=float,
        default=900.0,
        help="Max wait per job (provision/snapshot/reset/teardown).",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Polling interval for job status checks.",
    )
    parser.add_argument(
        "--blueprint-prefix",
        default="smoke-proxmox",
        help="Prefix used for temporary smoke blueprint name.",
    )
    parser.add_argument(
        "--allow-dry-run",
        action="store_true",
        help="Allow execution when /ops/health/hypervisor reports dry_run=True.",
    )
    parser.add_argument(
        "--skip-teardown",
        action="store_true",
        help="Skip teardown job during cleanup.",
    )
    parser.add_argument(
        "--keep-blueprint",
        action="store_true",
        help="Do not delete smoke blueprint after run.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return run_smoke(args)
    except SmokeTestError as exc:
        print(f"[smoke] FAILED: {exc}")
        return 1
    except requests.RequestException as exc:
        print(f"[smoke] FAILED (network): {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
