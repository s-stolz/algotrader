# Agent Bootstrap

This file is intentionally short because many coding agents auto-load it. Do not
turn it into full project documentation. Open deeper context only when relevant.

## First Reads

1. Read `CONTEXT.md` for project vocabulary, data contracts, and system flow.
2. Read `docs/CONTEXT-MAP.md` to choose the smallest task-specific context set.
3. For implementation work, open the nearest `<area>/CONTEXT.md` before editing.
4. For cross-service contract changes, open `docs/agent/CONTRACT-CHANGES.md`.

## Repository Shape

- `frontend/`: Vue 3 and Vite chart UI.
- `webserver/`: Python WebSocket bridge from Redis streams to frontend clients.
- `broker-service/`: FastAPI cTrader adapter, broker commands, and live stream publisher.
- `ingestion-service/`: Redis candle stream consumer and Timescale persistence worker.
- `database-accessor-api/`: FastAPI market and candle storage interface over TimescaleDB.
- `indicator-api/`: historical and live indicator calculation interface.
- `backtester/`: standalone Python backtesting module.
- `libs/`: shared Python libraries.
- `config/`: tracked topology and generated runtime env model.
- `timescaledb-init/`: database schema, hypertable, and continuous aggregate SQL.

## Hard Rules

- Never commit real secrets.
- Preserve the timestamp, Redis stream, and Timescale contracts in `CONTEXT.md`.
- Ignore generated/vendor paths unless debugging generated output: `.venv/`, `node_modules/`, `dist/`, `__pycache__/`, `.ruff_cache/`.

## Common Commands

- Full stack: `make up`
- Rebuild stack: `make up-build`
- Regenerate config: `make config`
- Backend tests: `make test`
- Frontend gate: `make test frontend`
- Python lint/format check: `./lint-python.sh`

More commands and per-area test commands live in `docs/agent/COMMANDS.md`.
The end-to-end agent workflow lives in `docs/agent/WORKFLOW.md`.

## Development Conventions

- Prefer existing module patterns over new architecture.
- For Python services, tests use `unittest` and service-local `tests/` or `test/`.
- For frontend changes, use Vitest and Vue Test Utils.
- When a cross-service contract changes, update the producer and consumer context files.
- Durable architecture decisions live in `docs/adr/`; check them before revisiting
  established seams.

Open `docs/agent/CODING-CONVENTIONS.md` only when editing code or tests.
