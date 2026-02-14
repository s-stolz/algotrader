PYTHON ?= python
COMPOSE ?= docker compose --env-file config/.env.shared

.PHONY: config validate-config up build down restart logs ps

config:
	$(PYTHON) scripts/generate_env.py --force

validate-config:
	$(PYTHON) scripts/generate_env.py --validate

up: config
	$(COMPOSE) up --build

build: config
	$(COMPOSE) build

down:
	$(COMPOSE) down

restart: config
	$(COMPOSE) down
	$(COMPOSE) up --build

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps
