# Orion Range Core Architecture (Fase 1)

## Visão Geral

codex/verify-the-structure-kqxjtv
A fase atual entrega a fundação do backend com FastAPI e quatro blocos principais:

- **API layer**: rotas de health, version, validação e CRUD de blueprint.
- **Domain schemas**: modelos Pydantic para blueprint de laboratório.
- **Services**: validação semântica de blueprints.
- **Store**: persistência em memória para ciclo de vida de blueprints (transitória).
main

## Estrutura

- `backend/app/main.py`: bootstrap da aplicação e registro de rotas.
- `backend/app/api/`: endpoints HTTP.
- `backend/app/schemas/`: contratos de dados.
codex/verify-the-structure-kqxjtv
- `backend/app/services/`: regras de negócio e store em memória.
- `backend/app/core/`: configurações e logging.

## Fluxo de validação e ciclo de blueprint

1. Cliente envia `POST /blueprints/validate` para validação semântica sem persistência.
2. Cliente envia `POST /blueprints` para criar blueprint válido na store em memória.
3. Cliente consulta blueprints com `GET /blueprints` e `GET /blueprints/{id}`.
4. Cliente remove blueprint com `DELETE /blueprints/{id}`.

## Regras semânticas de validação

- Nomes de redes únicos.
- Nomes de nós únicos.
- Nós só podem referenciar redes existentes.
- CIDR de rede deve ser válido quando informado.
- Cada nó deve referenciar ao menos uma rede e sem duplicações.

## Observação sobre persistência

A store atual é **em memória** e não persiste reinícios do processo. A próxima etapa do roadmap substitui essa camada por banco de dados.
main

## Execução local

- App: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (em `backend/`).
- Testes: `pytest` (em `backend/`).
- Docker Compose: `docker compose -f deploy/docker-compose.yml up --build`.
