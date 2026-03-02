codex/verify-the-structure-59nncd
# Orion Range Core Architecture (Fase 3)

## Visão Geral

A fase atual entrega backend FastAPI com validação semântica, persistência de blueprints e orquestração básica de jobs:
main

- **API layer**: rotas de health, version, validação e CRUD de blueprint.
- **Domain schemas**: modelos Pydantic para blueprint de laboratório.
- **Services**: validação semântica e repositório de blueprints.
codex/verify-the-structure-59nncd
- **Persistence**: SQLAlchemy ORM com tabelas `blueprints` e `jobs`.
- **Orchestration**: fila simples in-process para execução assíncrona com retry e timeout.
main

## Estrutura

- `backend/app/main.py`: bootstrap da aplicação, registro de rotas e criação de tabelas no startup.
- `backend/app/api/`: endpoints HTTP.
- `backend/app/schemas/`: contratos de dados.
- `backend/app/services/`: regras de negócio e acesso a dados.
codex/verify-the-structure-59nncd
- `backend/app/models/`: modelos ORM de blueprint e job.
- `backend/app/db/`: base ORM e sessão de banco.
main
- `backend/app/core/`: configurações e logging.

## Fluxo de validação e ciclo de blueprint

1. Cliente envia `POST /blueprints/validate` para validação semântica sem persistência.
codex/verify-the-structure-59nncd
2. Cliente envia `POST /blueprints` para criar blueprint válido no banco.
main
3. Cliente consulta blueprints com `GET /blueprints` e `GET /blueprints/{id}`.
4. Cliente remove blueprint com `DELETE /blueprints/{id}`.

## Regras semânticas de validação

- Nomes de redes únicos.
- Nomes de nós únicos.
- Nós só podem referenciar redes existentes.
- CIDR de rede deve ser válido quando informado.
- Cada nó deve referenciar ao menos uma rede e sem duplicações.

codex/verify-the-structure-59nncd
main
## Persistência e migração

- Banco configurado por `DATABASE_URL` (default local: SQLite).
- Compose de desenvolvimento inclui PostgreSQL.
- Migração inicial SQL em `backend/migrations/0001_create_blueprints.sql`.
codex/verify-the-structure-59nncd
main

## Execução local

- App: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (em `backend/`).
- Testes: `pytest` (em `backend/`).
- Docker Compose: `docker compose -f deploy/docker-compose.yml up --build`.
codex/verify-the-structure-59nncd


## Fluxo de jobs

1. Cliente envia `POST /jobs` com ação (`provision`, `snapshot`, `reset`) e blueprint opcional.
2. API cria job em `pending` e enfileira execução assíncrona.
3. Runner atualiza status (`running` -> `succeeded`/`failed`) com política de retry e timeout.
4. Cliente consulta progresso via `GET /jobs` e `GET /jobs/{id}`.
main
