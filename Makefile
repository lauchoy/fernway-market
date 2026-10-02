.PHONY: up down lint test

up:
	docker compose up -d --build --wait

down:
	docker compose down

lint:
	cd api && uv run --python 3.12 ruff check . && uv run --python 3.12 mypy && uv run --python 3.12 lint-imports
	cd web && npm run lint && npm run typecheck

test:
	cd api && uv run --python 3.12 pytest
	cd web && npm test
