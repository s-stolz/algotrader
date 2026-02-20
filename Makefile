PYTHON ?= python
COMPOSE ?= docker compose --env-file config/.env.shared
SERVICE ?=
DETACH ?= 0
UP_FLAGS ?=

.PHONY: ensure-pyyaml config validate-config up up-detached build down restart logs ps venvs venv venvs-recreate venvs-check

ifeq ($(DETACH),1)
UP_FLAGS += -d
endif

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
	$(COMPOSE) up --build $(UP_FLAGS)

up-detached: config
	$(COMPOSE) up --build -d

build: config
	$(COMPOSE) build

down:
	$(COMPOSE) down

restart: config
	$(COMPOSE) down
	$(COMPOSE) up --build $(UP_FLAGS)

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
