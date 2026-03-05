# Orion Range – Development Roadmap (ordered execution)

## Etapa 0 — Foundation and delivery reliability
- [x] FastAPI service bootstrap and core routes (`/health`, `/version`, `/blueprints/validate`).
- [x] Local container runtime (`backend/Dockerfile`, `deploy/docker-compose.yml`).
- [x] Basic test suite for health/version/blueprint validation.
- [x] CI workflow for backend (Python 3.11, compile check, pytest).
- [x] Makefile commands for common backend tasks.

## Etapa 1 — Blueprint contract hardening
- [x] Semantic validation service for duplicate names, unknown networks, CIDR parsing, and node-network requirements.
- [x] Add schema versioning field and migration notes.
- [x] Standardize API error codes for machine-consumable clients.

## Etapa 2 — Persistence layer
- [x] Add PostgreSQL service to compose stack.
- [x] Introduce ORM models and migrations.
- [x] Add CRUD endpoints for blueprint lifecycle.

## Etapa 3 — Job orchestration
- [x] Implement async job model (`pending/running/succeeded/failed`).
- [x] Add job submission/status endpoints.
- [x] Create worker execution loop with retry and timeout strategy.

## Etapa 4 — Hypervisor adapter (Proxmox-first)
- [x] Define hypervisor adapter interface.
- [x] Implement Proxmox adapter for clone/start/stop/snapshot actions.
- [x] Integrate adapter calls with job orchestrator.

## Etapa 5 — Baseline snapshot and deterministic reset
- [x] Baseline snapshot creation job.
- [x] Reset-to-baseline job.
- [x] Validation tests for repeatability and rollback behavior.

## Etapa 6 — Scenario simulation engine
- [x] Scenario schema (injects, timeline, preconditions).
- [x] Scenario executor and event tracking.
- [x] API endpoints for scenario start/stop/status.

## Etapa 7 — MITRE ATT&CK plugin support
- [x] Plugin interface for techniques.
- [x] Technique-to-action mapping and sample technique packages.

## Etapa 8 — Production hardening
- [ ] AuthN/AuthZ and multi-tenant boundaries.
  - [x] Initial API key protection for domain endpoints.
- [ ] Structured observability (metrics/tracing/log correlation).
- [ ] SLOs, alerts, and operational runbooks.


## Etapa 9 — Frontend operations console
- [x] Initial visual concept prototype (console selector + white team network view).
- [ ] Connect frontend to backend APIs (`/blueprints`, `/jobs`, `/scenarios`, `/mitre/techniques`).
  - [x] Initial `GET /mitre/techniques` integration in network console prototype.
  - [x] Initial scenario controls (`start/list/stop`) from frontend network console.
  - [x] Initial blueprints/jobs controls from frontend network console.
  - [x] Initial dynamic topology state + live events feed from runtime activity.
  - [x] Initial aggregated ops overview integration (`GET /ops/overview`).
- [ ] Real-time topology updates and scenario controls.
