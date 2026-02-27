# Orion Range

Orion Range is an open-source Cyber Range Orchestrator developed by Kra2Sec.

It enables organizations, universities, and security teams to build, execute, and reset realistic cybersecurity simulation environments using infrastructure-as-code principles and MITRE ATT&CK–aligned modeling.

---

## Overview

Modern security training environments are often built manually, making them difficult to reproduce, scale, or reset consistently.

Orion Range solves this by introducing:

- Structured Lab Blueprints (Lab-as-Code)
- Automated virtual machine provisioning
- Deterministic baseline snapshot and reset
- Modular architecture for attack technique modeling
- API-driven orchestration

Orion Range focuses on operational realism — modeling interconnected systems rather than isolated vulnerable machines.

---

## Core Features (Open-Source Core)

- Infrastructure Blueprint Engine
- Automated provisioning (Proxmox-first architecture)
- Baseline snapshot creation
- One-click deterministic reset
- Modular plugin system
- MITRE ATT&CK technique modeling (extensible)
- REST API for automation
- Community-driven templates

---

## Architecture Philosophy

Orion Range is built on three core principles:

### 1. Reproducibility
Every environment is defined as code and can be recreated consistently.

### 2. Modularity
Attack techniques, scenarios, and infrastructure components are implemented as extensible modules.

### 3. Operational Realism
The platform models complete environments composed of interconnected systems, networks, and behaviors.

---

## How It Works

1. Define a Lab Blueprint (JSON/YAML).
2. Orion Range provisions virtual machines via hypervisor integration.
3. A baseline snapshot is automatically created.
4. The lab can be reset to its original state deterministically.

Future releases will include scenario orchestration, inject events, scoring systems, and AI-assisted scenario generation.

---

## MITRE ATT&CK Integration

Orion Range is designed to be MITRE-native.

Attack techniques can be modeled as modular components and applied to nodes within a lab blueprint.

This allows structured adversary simulation aligned with established behavioral frameworks.

---

## Intended Use

Orion Range is intended exclusively for:

- Authorized cybersecurity training
- Academic research
- Defensive capability development
- Controlled simulation environments

It is not designed for offensive use outside authorized and legal environments.

---

codex/verify-the-structure-3amvss
main
## Development Execution Order

To deliver the project in full, execution follows `ROADMAP.md` in this order:

1. Foundation and delivery reliability
2. Blueprint contract hardening
3. Persistence layer
4. Job orchestration
5. Hypervisor adapter (Proxmox-first)
6. Baseline snapshot and deterministic reset
7. Scenario simulation engine
8. MITRE ATT&CK plugin support
9. Production hardening

---

codex/verify-the-structure-3amvss
main
## Roadmap

Planned milestones:

- MITRE technique plugin framework
- Scenario engine with inject support
- White Team operational control panel
- Multi-tenant orchestration
- AI-assisted blueprint generation
- Enterprise extensions (separate repository)

---

## Installation (Early Development)

> ⚠ Orion Range is currently under active development.

### Backend local run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

### Running tests

```bash
cd backend
pytest
```

### Docker Compose

```bash
docker compose -f deploy/docker-compose.yml up --build
```

---

## Contributing

We welcome community contributions.

Ways to contribute:

- Implement MITRE technique modules
- Improve blueprint validation
- Develop scenario templates
- Enhance orchestration features
- Improve documentation

Please read the CONTRIBUTING.md file before submitting pull requests.

---

## License

Orion Range Core is licensed under the Apache License 2.0.

Copyright (c) 2026 Kra2Sec.

Enterprise extensions and advanced orchestration modules are developed separately by Kra2Sec.

---

## Legal Notice

Orion Range is an independent open-source project developed by Kra2Sec.
It is not affiliated with any institutional cyber range platform.

---

## Maintained By

Kra2Sec  
https://kra2sec.com

Founder & Lead Maintainer: Ênio Krauss

---

## Vision

Our goal is to provide an open and extensible foundation for building structured cyber simulation environments — bridging the gap between isolated lab setups and full-scale operational cyber range platforms.

Orion Range aims to make advanced cyber training reproducible, scalable, and accessible.

---

