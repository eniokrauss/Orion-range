.PHONY: backend-setup backend-run backend-test backend-compile backend-ci backend-migrate-sql

backend-setup:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install '.[dev]'

backend-run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd backend && pytest

backend-compile:
	python -m compileall backend/app

backend-ci: backend-compile backend-test

backend-migrate-sql:
	@echo "Apply SQL files in backend/migrations with your DB client (psql)."
	@ls -1 backend/migrations/*.sql
