.PHONY: install dev pipeline test test-unit test-integration test-cov lint format migrate migrate-down docker-up docker-down docker-build

PYTHONPATH := $(shell pwd)

install:
	pip install -r requirements-dev.txt

dev:
	PYTHONPATH=$(PYTHONPATH) uvicorn src.api.main:app --reload --port 8000

pipeline:
	PYTHONPATH=$(PYTHONPATH) python -m src.pipeline.pipeline

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-cov:
	pytest tests/ --cov=src --cov-report=html

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

migrate:
	PYTHONPATH=$(PYTHONPATH) alembic upgrade head

migrate-down:
	PYTHONPATH=$(PYTHONPATH) alembic downgrade -1

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build
