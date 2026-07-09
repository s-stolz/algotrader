# Agent Commands

Run commands from the repository root unless noted.

## Full Stack

- Generate config: `make config`
- Validate config: `make validate-config`
- Start stack: `make up`
- Start rebuilt stack: `make up-build`
- Start detached: `make up-detached`
- Stop stack: `make down`
- View logs: `make logs`
- View containers: `make ps`
- Exercise asynchronous backtester success/failure paths: `make smoke-backtester`
- Apply pending TimescaleDB migrations to a running stack: `make migrate-db`

Direct Compose path:

```sh
make config
docker compose --env-file config/.env.shared up --build
```

Database migration path:

```sh
make up-detached
make migrate-db
```

## Python Environments

- Create all environments: `make venvs`
- Create root environment: `make venv-root`
- Create one service environment: `make venv SERVICE=broker-service`
- Recreate all environments: `make venvs-recreate`
- Validate environments: `make venvs-check`

## Test Commands

- All configured backend tests: `make test`
- Backtester: `make test backtester`
- Database accessor API: `make test database-accessor-api`
- Shared database accessor client: `make test db_accessor_client`
- Ingestion service: `make test ingestion-service`
- Broker service: `make test broker-service`
- Indicator engine: `make test indicator_engine`
- Frontend quality gate: `make test frontend`
- Full repository verification gate: `make verify`
- Python-only verification gate: `make verify-python`
- Timescale migration integration tests (running local stack):
  `RUN_MIGRATION_INTEGRATION_TESTS=1 .venv/bin/python -m unittest scripts.tests.test_migrations_integration`

Prefer `make` targets. Inspect `Makefile` only when debugging a target itself.

## Documentation Changes

For markdown-only changes, application tests are usually unnecessary. Verify that
the context map, ADR links, and referenced files still line up with the edited
workflow.

## Frontend

```sh
cd frontend && npm run dev
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run test:unit
cd frontend && npm run build
```

## Python Quality

```sh
./lint-python.sh
make typecheck-python
```

## Local Service Entrypoints

```sh
cd broker-service && uvicorn app.main:app --host 0.0.0.0 --port 8050
cd backtester && python main.py        # API
cd backtester && python worker.py      # singleton worker
cd webserver && python main.py
cd ingestion-service && python main.py
```
