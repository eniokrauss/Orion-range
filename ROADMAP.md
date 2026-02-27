# Orion Range – Development Roadmap (ordered execution)

## Etapa 0 — Foundation and delivery reliability
- [x] FastAPI service bootstrap and core routes (`/health`, `/version`, `/blueprints/validate`).
- [x] Local container runtime (`backend/Dockerfile`, `deploy/docker-compose.yml`).
- [x] Basic test suite for health/version/blueprint validation.
- [x] CI workflow for backend (Python 3.11, compile check, pytest).
- [x] Makefile commands for common backend tasks.

## Etapa 1 — Blueprint contract hardening
- [x] Semantic validation service for duplicate names, unknown networks, CIDR parsing, and node-network requirements.
- [ ] Add schema versioning field and migration notes.
- [ ] Standardize API error codes for machine-consumable clients.

## Etapa 2 — Persistence layer
- [ ] Add PostgreSQL service to compose stack.
- [ ] Introduce ORM models and migrations.
- [ ] Add CRUD endpoints for blueprint lifecycle.

## Etapa 3 — Job orchestration
- [ ] Implement async job model (`pending/running/succeeded/failed`).
- [ ] Add job submission/status endpoints.
- [ ] Create worker execution loop with retry and timeout strategy.

## Etapa 4 — Hypervisor adapter (Proxmox-first)
- [ ] Define hypervisor adapter interface.
- [ ] Implement Proxmox adapter for clone/start/stop/snapshot actions.
- [ ] Integrate adapter calls with job orchestrator.

## Etapa 5 — Baseline snapshot and deterministic reset
- [ ] Baseline snapshot creation job.
- [ ] Reset-to-baseline job.
- [ ] Validation tests for repeatability and rollback behavior.

## Etapa 6 — Scenario simulation engine
- [ ] Scenario schema (injects, timeline, preconditions).
- [ ] Scenario executor and event tracking.
- [ ] API endpoints for scenario start/stop/status.

## Etapa 7 — MITRE ATT&CK plugin support
- [ ] Plugin interface for techniques.
- [ ] Technique-to-action mapping and sample technique packages.

## Etapa 8 — Production hardening
- [ ] AuthN/AuthZ and multi-tenant boundaries.
- [ ] Structured observability (metrics/tracing/log correlation).
- [ ] SLOs, alerts, and operational runbooks.
