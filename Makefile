.PHONY: up down lint test

web/node_modules: web/package-lock.json web/package.json
	cd web && npm ci && touch node_modules

up:
	docker compose up -d --build --wait

down:
	docker compose down

lint: web/node_modules
	cd api && uv run --python 3.12 ruff check . && uv run --python 3.12 mypy && uv run --python 3.12 lint-imports
	cd web && npm run lint && npm run typecheck

test: web/node_modules
	cd api && uv run --python 3.12 pytest
	cd web && npm test
