# Context Map

Use this file to open only the context needed for the current task. Do not read
every file by default.

## Start Here

- `CONTEXT.md`: domain vocabulary, system flow, and cross-service data contracts.
- `AGENTS.md`: auto-loaded bootstrap; open only when editing it.
- `docs/agent/WORKFLOW.md`: full agent workflow; open when the process is unclear.

## Task Routing

| Task mentions | Open these first |
| --- | --- |
| chart, UI, watchlist, upload, WebSocket client | `frontend/CONTEXT.md`, then relevant files under `frontend/src/` |
| WebSocket bridge, subscriptions, fanout, Redis consumers | `webserver/CONTEXT.md`, `frontend/CONTEXT.md` if protocol touches UI |
| cTrader, broker, account, order, position, deal, tick stream, trendbar stream | `broker-service/CONTEXT.md` |
| Redis candle ingestion, startup backfill, recovery backfill, writing candles | `ingestion-service/CONTEXT.md`, `database-accessor-api/CONTEXT.md` |
| markets, candles storage, TimescaleDB, continuous aggregates | `database-accessor-api/CONTEXT.md`, `timescaledb-init/CONTEXT.md` |
| indicators, live indicator stream, historical indicator response | `indicator-api/CONTEXT.md`, `libs/CONTEXT.md` |
| backtesting, strategy, fills, portfolio, metrics | `backtester/CONTEXT.md`, `libs/CONTEXT.md` |
| shared Python clients or indicator engine | `libs/CONTEXT.md` |
| topology, env generation, Docker compose ports | `config/CONTEXT.md`, `docker-compose.yml`, `scripts/generate_env.py` |
| schema bootstrap, hypertables, aggregate policies | `timescaledb-init/CONTEXT.md` |
| cross-service contract change | `docs/agent/CONTRACT-CHANGES.md`, then affected producer and consumer contexts |
| architecture decision or revisiting an established seam | `docs/adr/README.md`, then relevant ADR files |
| build, run, test, local service command | `docs/agent/COMMANDS.md` |
| code style, test placement, repo conventions | `docs/agent/CODING-CONVENTIONS.md` |

## Existing Reference Docs

- `README.md`: human-facing product overview and local setup. Prefer context docs
  for agent routing and cross-service contracts.
- `broker-service/README.md`: detailed human-facing broker runtime and
  configuration reference.
- `webserver/README.md`: WebSocket bridge overview. Prefer current code and
  `webserver/CONTEXT.md` for protocol changes.
- `ingestion-service/README.md`: ingestion overview.
- `libs/indicator_engine/README.md`: indicator engine concepts and examples.
- `backtester/backtester_design.md`: backtester target architecture.
- `backtester/backtester_implementation_plan.md`: historical migration and
  roadmap context; do not treat it as the active task queue.

## Maintenance

- Avoid `.venv/`, `node_modules/`, `dist/`, `.ruff_cache/`, and `__pycache__/`
  unless a generated artifact is the task.
- If a contract changes, update both the producer and consumer context files.
- If a new durable architecture decision is made, add an ADR under `docs/adr/`
  and link it from `docs/adr/README.md`.
