SHELL := /bin/sh

infra:
	docker compose up -d postgres redis minio minio-init

migrate:
	cd services/api && uv run alembic upgrade head

api:
	cd services/api && uv run fastapi dev app/main.py

worker:
	cd services/api && uv run python -m app.worker.main

web:
	cd apps/web && npm run dev

test:
	cd services/api && uv run pytest

lint:
	cd services/api && uv run ruff check app tests
	cd apps/web && npm run lint

build:
	cd apps/web && npm run build

all:
	docker compose --profile app up --build
