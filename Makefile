ifneq ($(wildcard .venv/bin/python),)
PYTHON ?= .venv/bin/python
else
PYTHON ?= python
endif
COMPOSE ?= docker compose --env-file config/.env.shared
SERVICE ?=
DETACH ?= 0
UP_FLAGS ?=

TEST_BACKEND ?= all
TEST_BACKEND_FROM_GOAL := $(firstword $(filter-out test,$(MAKECMDGOALS)))
ifneq ($(strip $(TEST_BACKEND_FROM_GOAL)),)
TEST_BACKEND := $(TEST_BACKEND_FROM_GOAL)
endif

.PHONY: ensure-pyyaml config validate-config smoke-backtester up up-detached up-build up-build-detached build down restart logs ps venvs venv venv-root venvs-recreate venvs-check typecheck-python verify-python verify test backtester database-accessor-api db_accessor_client ingestion-service broker-service indicator_engine frontend

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
	$(PYTHON) -m unittest discover -s scripts/tests -t . -p "test_*.py"
	$(PYTHON) scripts/generate_env.py --validate

smoke-backtester: config
	@(cd backtester && \
		py_bin="$(PYTHON)"; \
		[ ! -x "$$py_bin" ] && py_bin="python"; \
		[ -x .venv/bin/python ] && py_bin=".venv/bin/python"; \
		set -a; . ../config/.env.shared; set +a; \
		PYTHONPATH=src $$py_bin smoke.py)

up: config
	$(COMPOSE) up $(UP_FLAGS)

up-detached: config
	$(COMPOSE) up -d

up-build: config
	$(COMPOSE) up --build $(UP_FLAGS)

up-build-detached: config
	$(COMPOSE) up --build -d

build: config
	$(COMPOSE) build

down:
	$(COMPOSE) down

restart: config
	$(COMPOSE) down
	$(COMPOSE) up $(UP_FLAGS)

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

venvs:
	./scripts/setup_venvs.sh all

venv:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make venv SERVICE=<service-name|root>"; \
		exit 1; \
	fi
	./scripts/setup_venvs.sh $(SERVICE)

venv-root:
	./scripts/setup_venvs.sh root

venvs-recreate:
	./scripts/setup_venvs.sh --recreate all

venvs-check:
	./scripts/check_venvs.sh all

typecheck-python:
	./scripts/typecheck_python.sh

verify-python:
	./lint-python.sh
	$(MAKE) typecheck-python
	$(MAKE) test

verify:
	$(MAKE) verify-python
	$(MAKE) test frontend

test:
	@status=0; \
	if [ "$(TEST_BACKEND)" = "all" ] || [ "$(TEST_BACKEND)" = "backtester" ]; then \
		echo "Running backtester tests..."; \
		(cd backtester && py_bin="$(PYTHON)"; [ ! -x "$$py_bin" ] && py_bin="python"; [ -x .venv/bin/python ] && py_bin=".venv/bin/python"; PYTHONPATH=src $$py_bin -m unittest discover -s tests -t . -p "test_*.py") || status=1; \
	fi; \
	if [ "$(TEST_BACKEND)" = "all" ] || [ "$(TEST_BACKEND)" = "database-accessor-api" ]; then \
		echo "Running database-accessor-api tests..."; \
		(cd database-accessor-api && py_bin="$(PYTHON)"; [ ! -x "$$py_bin" ] && py_bin="python"; [ -x .venv/bin/python ] && py_bin=".venv/bin/python"; $$py_bin -m unittest discover -s tests -p "test_*.py") || status=1; \
	fi; \
	if [ "$(TEST_BACKEND)" = "all" ] || [ "$(TEST_BACKEND)" = "db_accessor_client" ]; then \
		echo "Running db_accessor_client tests..."; \
		(cd libs/db_accessor_client && py_bin="../../$(PYTHON)"; [ ! -x "$$py_bin" ] && py_bin="$(PYTHON)"; [ ! -x "$$py_bin" ] && py_bin="python"; PYTHONPATH=. $$py_bin -m unittest discover -s tests -p "test_*.py") || status=1; \
	fi; \
	if [ "$(TEST_BACKEND)" = "all" ] || [ "$(TEST_BACKEND)" = "ingestion-service" ]; then \
		echo "Running ingestion-service tests..."; \
		(cd ingestion-service && py_bin="$(PYTHON)"; [ ! -x "$$py_bin" ] && py_bin="python"; [ -x .venv/bin/python ] && py_bin=".venv/bin/python"; $$py_bin -m unittest discover -s tests -p "test_*.py") || status=1; \
	fi; \
	if [ "$(TEST_BACKEND)" = "all" ] || [ "$(TEST_BACKEND)" = "broker-service" ]; then \
		echo "Running broker-service tests..."; \
		(cd broker-service && py_bin="$(PYTHON)"; [ ! -x "$$py_bin" ] && py_bin="python"; [ -x .venv/bin/python ] && py_bin=".venv/bin/python"; $$py_bin -m unittest discover -s tests -p "test_*.py") || status=1; \
	fi; \
	if [ "$(TEST_BACKEND)" = "all" ] || [ "$(TEST_BACKEND)" = "indicator_engine" ]; then \
		echo "Running indicator_engine tests..."; \
		(cd libs/indicator_engine && py_bin="$(PYTHON)"; [ ! -x "$$py_bin" ] && py_bin="python"; [ -x .venv/bin/python ] && py_bin=".venv/bin/python"; $$py_bin -m unittest discover -s tests -p "test_*.py") || status=1; \
	fi; \
	if [ "$(TEST_BACKEND)" = "frontend" ]; then \
		echo "Running frontend quality gate..."; \
		npm --prefix frontend run lint || status=1; \
		npm --prefix frontend run typecheck || status=1; \
		npm --prefix frontend run test:layout || status=1; \
		npm --prefix frontend run test:unit || status=1; \
		npm --prefix frontend run build || status=1; \
	fi; \
	if [ "$(TEST_BACKEND)" != "all" ] && [ "$(TEST_BACKEND)" != "backtester" ] && [ "$(TEST_BACKEND)" != "database-accessor-api" ] && [ "$(TEST_BACKEND)" != "db_accessor_client" ] && [ "$(TEST_BACKEND)" != "ingestion-service" ] && [ "$(TEST_BACKEND)" != "broker-service" ] && [ "$(TEST_BACKEND)" != "indicator_engine" ] && [ "$(TEST_BACKEND)" != "frontend" ]; then \
		echo "Invalid test target '$(TEST_BACKEND)'. Use: make test [backtester|database-accessor-api|db_accessor_client|ingestion-service|broker-service|indicator_engine|frontend]"; \
		exit 1; \
	fi; \
	exit $$status

backtester database-accessor-api db_accessor_client ingestion-service broker-service indicator_engine frontend:
	@:
