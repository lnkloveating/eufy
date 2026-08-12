.PHONY: help backend-install backend-test backend-lint frontend-install frontend-test frontend-lint

help:
	@echo "This repository is currently a skeleton. See README.md."

backend-install:
	cd backend && python -m pip install -e ".[dev]"

backend-test:
	cd backend && pytest

backend-lint:
	cd backend && ruff check . && mypy src

frontend-install:
	cd frontend && npm install

frontend-test:
	cd frontend && npm test

frontend-lint:
	cd frontend && npm run lint
