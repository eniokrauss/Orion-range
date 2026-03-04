# Orion Range Core Architecture (Fase 7)

## Visão Geral

A fase atual entrega backend FastAPI com validação semântica, persistência de blueprints, orquestração de jobs e execução de cenários com mapeamento MITRE:

- **API layer**: rotas de health, version, blueprint validate/CRUD, jobs e scenarios.
- **Domain schemas**: modelos Pydantic para blueprint, job e scenario.
- **Services**: validação semântica, repositórios e runners assíncronos.
- **Persistence**: SQLAlchemy ORM com tabelas `blueprints`, `jobs`, `baselines` e `scenario_runs`.
- **Orchestration**: fila in-process para execução assíncrona com retry e timeout.
- **Hypervisor Adapter**: interface + adapter Proxmox-first integrado ao runner de jobs.
- **Scenario Engine**: execução assíncrona de cenários com timeline e controle start/stop/status.
- **MITRE Plugin Registry**: resolução de ações `mitre:<technique_id>` para ações executáveis e descoberta de técnicas carregadas via API.

## Estrutura

- `backend/app/main.py`: bootstrap da aplicação, registro de rotas e criação de tabelas no startup.
- `backend/app/api/`: endpoints HTTP.
- `backend/app/schemas/`: contratos de dados.
- `backend/app/services/`: regras de negócio e acesso a dados.
- `backend/app/models/`: modelos ORM.
- `backend/app/db/`: base ORM e sessão de banco.
- `backend/app/core/`: configurações, logging e contrato de erros.

## Contrato de blueprint

- Campo `schema_version` em `LabBlueprint` para evolução do contrato.
- Versões suportadas atualmente: `1.0`.
- Versão não suportada retorna erro 400 com `detail.code=UNSUPPORTED_BLUEPRINT_SCHEMA`.

## Erros padronizados (machine-consumable)

Todas as rotas de domínio retornam erros com estrutura:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "mensagem legível"
  }
}
```

Exemplos:
- `UNKNOWN_NETWORK_REFERENCE`
- `INVALID_CIDR`
- `NODE_WITHOUT_NETWORK`
- `NOT_FOUND`

## Segurança de API (etapa 8 inicial)

- Quando `API_KEY` está configurada, rotas de domínio (`/blueprints`, `/jobs`, `/scenarios`) exigem header `x-api-key`.
- Rotas de observabilidade/meta (`/health`, `/version`) permanecem públicas para monitoramento.
- Falhas de autenticação retornam `401` com `detail.code=UNAUTHORIZED`.

## Persistência e migrações

- Banco configurado por `DATABASE_URL` (default local: SQLite).
- Compose de desenvolvimento inclui PostgreSQL.
- Migrações SQL versionadas:
  - `backend/migrations/0001_create_blueprints.sql`
  - `backend/migrations/0002_create_jobs.sql`
  - `backend/migrations/0004_create_baselines.sql`
  - `backend/migrations/0005_create_scenario_runs.sql`

## Fluxo de validação e ciclo de blueprint

1. Cliente envia `POST /blueprints/validate` para validação semântica sem persistência.
2. Cliente envia `POST /blueprints` para criar blueprint válido no banco.
3. Cliente consulta blueprints com `GET /blueprints` e `GET /blueprints/{id}`.
4. Cliente remove blueprint com `DELETE /blueprints/{id}`.

## Fluxo de jobs

1. Cliente envia `POST /jobs` com ação (`provision`, `snapshot`, `reset`) e blueprint opcional.
2. API cria job em `pending` e enfileira execução assíncrona.
3. Runner atualiza status (`running` -> `succeeded`/`failed`) com política de retry e timeout.
4. Cliente consulta progresso via `GET /jobs` e `GET /jobs/{id}`.

## Fluxo de baseline e reset

1. `POST /jobs` com ação `snapshot` cria/atualiza baseline do blueprint.
2. `POST /jobs` com ação `reset` exige baseline prévio e incrementa contador de reset.
3. Repetição de reset no mesmo baseline mantém execução determinística do fluxo.


## Fluxo de descoberta MITRE

1. Cliente consulta `GET /mitre/techniques`.
2. API retorna técnicas carregadas por plugin (`plugin`, `technique_id`, `name`, `tactics`, `action`).
3. Frontend pode usar essa lista para popular construtor de cenários com técnicas suportadas.

## Fluxo de cenários

1. Cliente envia `POST /scenarios/runs` com nome do cenário e passos.
2. Runner processa passos e atualiza status (`pending`/`running`/`completed`/`stopped`/`failed`).
3. Passos `mitre:<technique_id>` são resolvidos para ação concreta via plugin.
4. Cliente consulta via `GET /scenarios/runs` e `GET /scenarios/runs/{id}`.
5. Cliente pode interromper com `POST /scenarios/runs/{id}/stop`.

## Execução local

- App: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (em `backend/`).
- Testes: `pytest` (em `backend/`).
- Docker Compose: `docker compose -f deploy/docker-compose.yml up --build`.
