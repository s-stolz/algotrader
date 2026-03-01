# Repository Guidelines

## Project Structure & Module Organization
This repo is a multi-service trading platform.
- `frontend/`: Vue 3 + Vite UI (`src/components`, `src/views`, `src/stores`, `src/utils`).
- `database-accessor-api/`, `indicator-api/`, `broker-service/`: FastAPI microservices.
- `webserver/`: Python WebSocket bridge to Redis/broker APIs.
- `ingestion-service/`: ingestion worker for market data.
- `backtester/`: standalone Python backtesting module (`src/`, `test/`).
- `timescaledb-init/`: DB bootstrap SQL.
- `docker-compose.yml`: local orchestration entrypoint.

## Build, Test, and Development Commands
- `make up`: generate config env files and run full stack (`docker compose up --build`).
- `make config`: regenerate config env files from `config/topology.yaml` and `config/.env.secrets.local`.
- `docker compose up --build`: build and run the full stack (run `make config` first).
- `npm --workspace frontend run dev`: start frontend dev server.
- `npm --workspace frontend run build`: production frontend build.
- `npm --workspace frontend run lint`: lint JS/Vue code.
- `./lint-python.sh`: run Ruff and Black checks across Python services.
- `cd backtester && python main.py`: run backtester locally.
- `cd broker-service && uvicorn app.main:app --host 0.0.0.0 --port 8050`: run broker API locally.

## Coding Style & Naming Conventions
- Python: 4-space indentation, `snake_case` functions/variables, `PascalCase` classes, max line length 100 (see `pyproject.toml` and `webserver/pyproject.toml`).
- Vue/JS: follow `frontend/eslint.config.mjs`; semicolons required, trailing commas on multiline structures, kebab-case custom event names.
- Keep modules focused by domain (`api/`, `application/`, `domain/`, `infrastructure/` pattern in `broker-service`).

## Testing Guidelines
- Automated tests currently include:
  - `backtester/test/signals/test_signals.py` (unittest)
  - `broker-service/tests/` (unittest; structure mirrors `broker-service/app/`)
- Run:
  - `python -m unittest backtester/test/signals/test_signals.py`
  - `cd broker-service && python -m unittest discover -s tests -p "test_*.py"`
- For new Python tests, prefer `test_*.py` naming and colocate under each service’s `test/` or `tests/` directory mirroring source structure.
- Add API contract/integration tests for new endpoints and stream behavior.

## Security & Configuration Tips
- Never commit real secrets.
- Use centralized config:
  - Tracked shared topology: `config/topology.yaml`
  - Local secrets (gitignored): `config/.env.secrets.local` (copy from `config/.env.secrets.example`)
  - Generated runtime env files (gitignored): `config/.env.shared`, `config/.env.secrets.db`, `config/.env.secrets.runtime`, `config/.env.secrets.broker` via `python scripts/generate_env.py`
- Validate port and healthcheck changes against `docker-compose.yml` before merging.

## Timestamp & Timezone Convention
- External/internal API contracts use UTC epoch milliseconds only (`timestamp_ms`, `start_ms`, `end_ms`).
- Redis stream payloads stay compact and use one-character keys only:
  - ticks: `b`, `a`, `t`
  - candles: `o`, `h`, `l`, `c`, `v`, `t`
- TimescaleDB stores candle time in `candles.timestamp_utc` (`TIMESTAMPTZ`).
- `markets.timezone` stores IANA timezone IDs (e.g. `Europe/Berlin`) for market/session logic only; transport/storage timestamps remain UTC.
