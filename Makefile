.PHONY: backend-setup backend-run backend-test backend-compile backend-ci

backend-setup:
codex/verify-the-structure-kqxjtv
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install '.[dev]'
main

backend-run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd backend && pytest

backend-compile:
	python -m compileall backend/app

backend-ci: backend-compile backend-test
