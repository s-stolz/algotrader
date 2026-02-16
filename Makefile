PYTHON ?= python
COMPOSE ?= docker compose --env-file config/.env.shared
SERVICE ?=

.PHONY: ensure-pyyaml config validate-config up build down restart logs ps venvs venv venvs-recreate venvs-check

ensure-pyyaml:
	@$(PYTHON) -c "import yaml" >/dev/null 2>&1 || { \
		echo "PyYAML missing for $(PYTHON); installing..."; \
		$(PYTHON) -m pip install pyyaml; \
	}

config: ensure-pyyaml
	$(PYTHON) scripts/generate_env.py --force

validate-config: ensure-pyyaml
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

venvs:
	./scripts/setup_venvs.sh all

venv:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make venv SERVICE=<service-name>"; \
		exit 1; \
	fi
	./scripts/setup_venvs.sh $(SERVICE)

venvs-recreate:
	./scripts/setup_venvs.sh --recreate all

venvs-check:
	./scripts/check_venvs.sh all
