# Orion Range – Development Roadmap

## Etapa 0 — Foundation and delivery reliability
- [x] FastAPI service bootstrap and core routes (`/health`, `/version`, `/blueprints/validate`).
- [x] Local container runtime (`backend/Dockerfile`, `deploy/docker-compose.yml`).
- [x] Basic test suite for health/version/blueprint validation.
- [x] CI workflow for backend (Python 3.11, compile check, pytest).
- [x] Makefile commands for common backend tasks.

## Etapa 1 — Blueprint contract hardening
- [x] Semantic validation: duplicate names, unknown networks, CIDR parsing, node-network requirements.
- [x] Schema versioning field and migration notes.
- [x] Standardized API error codes for machine-consumable clients.

## Etapa 2 — Persistence layer
- [x] PostgreSQL service in compose stack.
- [x] ORM models and SQL migrations (0001–0008).
- [x] CRUD endpoints for blueprint lifecycle.
- [x] `org_id` column on all domain tables (migration 0007) — multi-tenant foundation.

## Etapa 3 — Job orchestration
- [x] Async job model (`pending/running/succeeded/failed`).
- [x] Job submission/status/list endpoints.
- [x] Worker execution loop with per-action retry and timeout.
- [x] `teardown` action added to job runner.
- [x] `GET /jobs/{id}/steps` endpoint for checkpoint visibility.

## Etapa 4 — Hypervisor adapter (Proxmox-first)
- [x] `HypervisorAdapter` abstract interface with `provision/snapshot/reset/teardown/health_check`.
- [x] `ProxmoxAdapter` real implementation (proxmoxer, async task polling, dry-run mode).
- [x] Configurable timeouts per operation via settings (provision=600s, snapshot=120s, reset=180s).
- [x] Idempotent provision: existing VMs are skipped, not duplicated.
- [x] `health_check()` endpoint-ready, returns Proxmox version info.

## Etapa 5 — Baseline snapshot and deterministic reset
- [x] Baseline snapshot creation (`snapshot` job).
- [x] Reset-to-baseline (`reset` job) with repeat-count tracking.
- [x] Full lifecycle tests: provision → snapshot → reset × N.

## Etapa 6 — Checkpoint-based job recovery
- [x] `JobStep` model and `job_steps` table (migration 0006).
- [x] `JobStepRepository` with `get_or_create / mark_running / mark_done / mark_failed / is_done`.
- [x] Checkpoint loop in job runner: done steps skipped on retry/recovery.
- [x] Step plan per action: named atomic steps in ordered DAG.
- [x] `GET /jobs/{id}/steps` exposes step state for debugging and observability.
- [x] Full unit test coverage: retry, recovery, failure marking, dedup guard.

## Etapa 7 — Scenario simulation engine
- [x] Scenario schema (steps, timeline, delays).
- [x] Scenario executor with stop event, timeline tracking, event streaming.
- [x] API endpoints for scenario start/stop/status.

## Etapa 8 — MITRE ATT&CK plugin support
- [x] Plugin interface (`MitrePlugin` protocol) with `resolve / list_techniques`.
- [x] Builtin plugin: T1566 (Phishing), T1110 (Brute Force), T1041 (C2 Exfil).
- [x] Extensible registry — new plugins register at startup.

## Etapa 9 — Production hardening
- [x] Full AuthN/AuthZ with JWT (Bearer tokens, HS256, access+refresh).
- [x] Multi-tenant RBAC: `org_id` on all models, `require_roles()` factory, `range_admin/instructor/student`.
- [x] Structured log correlation: `job_id`, `org_id`, `blueprint_id`, `step_key`, `request_id` in every log line.
- [x] Garbage collector for orphaned Proxmox resources (`GET /ops/gc` dry-run, `POST /ops/gc` delete).
- [x] Periodic GC background thread (configurable via `GC_INTERVAL_SECONDS`).
- [ ] SLOs and alerting runbooks.

## Etapa 10 — Ops observability
- [x] `/metrics` Prometheus endpoint (HTTP counters by path/status).
- [x] `x-request-id` correlation header on every response.
- [x] `/ops/overview` aggregates real DB data (fake telemetry removed).
- [x] Job retry events surfaced with `warn` level in ops event feed.
- [x] Prometheus metrics for job duration histogram, step count by action/status, reset latency histogram.
- [x] `GET /ops/health/hypervisor` — live hypervisor connectivity check.
- [ ] OpenTelemetry tracing.

## Etapa 11 — Frontend operations console
- [x] Console selector (White/Red/Blue team entry points).
- [x] White Team network console with blueprint/job/scenario controls.
- [x] MITRE techniques integration in network console.
- [x] Ops overview integration — stats bar now shows real data from `/ops/overview`.
- [x] `teardown` action available in job submission UI.
- [x] Job checkpoint steps panel: click "steps" on any job to see step-by-step progress.
- [x] GC dry-run panel: "GC dry-run" button calls `GET /ops/gc` and shows orphaned VMs.
- [ ] Real-time topology updates via WebSocket.
- [ ] Red Team and Blue Team consoles.
