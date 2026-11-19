.PHONY: up down logs test lint seed migrate install-dev

up:
	docker compose -f infra/docker-compose.yml up --build -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f --tail=100

install-dev:
	python3 -m pip install -e 'services/api[dev]' -e 'services/agents[dev]' -e 'services/model[dev]'

test:
	PYTHONPATH=services/api/src:services/agents/src:services/model/src python3 -m pytest services/api/tests services/agents/tests services/model/tests

lint:
	python -m ruff check services/api services/agents services/model

seed:
	docker compose -f infra/docker-compose.yml exec api python -m liveslide_api.cli seed

migrate:
	docker compose -f infra/docker-compose.yml exec api alembic upgrade head
