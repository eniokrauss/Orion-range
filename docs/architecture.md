# Orion Range Core Architecture (Fase 1)

## Visão Geral

A fase atual entrega a fundação do backend com FastAPI e três blocos principais:

- **API layer**: rotas de health, version e validação de blueprint.
- **Domain schemas**: modelos Pydantic para blueprint de laboratório.
- **Services**: validação semântica de blueprints.

## Estrutura

- `backend/app/main.py`: bootstrap da aplicação e registro de rotas.
- `backend/app/api/`: endpoints HTTP.
- `backend/app/schemas/`: contratos de dados.
- `backend/app/services/`: regras de negócio.
- `backend/app/core/`: configurações e logging.

## Fluxo de validação de Blueprint

1. Cliente envia `POST /blueprints/validate`.
2. API desserializa payload para `LabBlueprint` (Pydantic).
3. Serviço `validate_blueprint` executa regras semânticas:
   - Nomes de redes únicos.
   - Nomes de nós únicos.
   - Nós só podem referenciar redes existentes.
   - CIDR de rede deve ser válido quando informado.
   - Cada nó deve referenciar ao menos uma rede e sem duplicações.
4. API retorna:
   - `200` com resumo (`name`, `version`, `nodes`, `networks`).
   - `400` com detalhe textual de erro quando inválido.

## Execução local

- App: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (em `backend/`).
- Testes: `pytest` (em `backend/`).
- Docker Compose: `docker compose -f deploy/docker-compose.yml up --build`.
