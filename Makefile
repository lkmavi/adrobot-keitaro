.PHONY: help install lint format format-check typecheck test test-unit test-integration coverage coverage-html check db-upgrade db-current run docker-build docker-up docker-down logs logs-stack

.DEFAULT_GOAL := help

help:
	@printf '%s\n' \
	  'make install          Установить зависимости' \
	  'make check            Запустить все проверки и тесты с покрытием' \
	  'make lint             Проверить код Ruff' \
	  'make format           Отформатировать код Ruff' \
	  'make format-check     Проверить форматирование' \
	  'make typecheck        Проверить типы mypy' \
	  'make test             Запустить все тесты' \
	  'make test-unit        Запустить модульные тесты' \
	  'make test-integration Запустить интеграционные тесты с Docker' \
	  'make coverage         Запустить тесты с отчётом покрытия' \
	  'make coverage-html    Создать HTML-отчёт покрытия' \
	  'make db-upgrade       Применить миграции к локальной базе' \
	  'make db-current       Показать версию схемы базы' \
	  'make run              Запустить приложение локально' \
	  'make docker-build     Собрать Docker-образ' \
	  'make docker-up        Запустить приложение в Docker Compose' \
	  'make docker-down      Остановить контейнеры без удаления данных' \
	  'make logs             Следить за логами приложения' \
	  'make logs-stack       Посмотреть состояние сборщика и хранилища'

install:
	uv sync --frozen

lint:
	uv run --frozen ruff check .

format:
	uv run --frozen ruff format .

format-check:
	uv run --frozen ruff format --check .

typecheck:
	uv run --frozen mypy app

test:
	uv run --frozen pytest -q

test-unit:
	uv run --frozen pytest tests/unit -q

test-integration:
	uv run --frozen pytest tests/integration -q

coverage:
	uv run --frozen pytest -q --cov=app --cov-report=term-missing

coverage-html:
	uv run --frozen pytest -q --cov=app --cov-report=html

check:
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) typecheck
	$(MAKE) coverage

db-upgrade:
	uv run --frozen alembic upgrade head

db-current:
	uv run --frozen alembic current

run:
	uv run --frozen alembic upgrade head
	uv run --frozen uvicorn app.main:app --reload

docker-build:
	docker compose build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

logs:
	docker compose logs -f web

logs-stack:
	docker compose logs --tail=100 alloy loki grafana
