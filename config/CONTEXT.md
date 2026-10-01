# Configuration Context

Centralized non-secret topology plus generated runtime environment files.

## Owned Interfaces

- Tracked non-secret topology in `topology.yaml`.
- Gitignored local secret input and generated runtime env outputs.
- Validation and generation behavior in `scripts/generate_env.py`.
- Docker Compose and local process environment contracts.

## Key Files

- `topology.yaml`: tracked shared topology for hosts, ports, logging, Redis,
  TimescaleDB, per-container Docker resources, broker limits, backtester worker polling, and
  ingestion/webserver knobs.
- `topology.local.yaml`: optional gitignored partial machine overrides; recursive
  merge over tracked defaults, explicit null replaces defaults, unknown keys rejected.
- `topology.local.example.yaml`: tracked override template.
- `.env.secrets.example`: template for local secrets.
- `.env.secrets.local`: local secrets, gitignored.
- `.env.shared`: generated shared runtime env, gitignored.
- `.env.secrets.db`: generated database secret env, gitignored.
- `.env.secrets.runtime`: generated runtime secret env, gitignored.
- `.env.secrets.broker`: generated broker secret env, gitignored.
- `scripts/generate_env.py`: generator and validation logic.

## Contracts

- Run `make config` or `python scripts/generate_env.py --force` after topology or
  secrets changes.
- Run `make validate-config` or `python scripts/generate_env.py --validate` to
  check required secret values.
- Docker Compose uses `config/.env.shared` plus service-specific secret env files.
- Topology has four root keys: `mode`, `public`, `services`, and `infrastructure`.
  Each component owns `network`, `logging`, `resources`, and named runtime tuning
  groups where applicable. `services.backtester` groups its `api` and `worker`
  processes with shared `logging` and `sweeps` settings. Worker-only components
  have no network endpoint. See `topology.schema.md` for exact paths.
- Each container's `resources` mapping generates the existing
  `COMPOSE_<SERVICE>_CPUS` and `COMPOSE_<SERVICE>_MEMORY_RESERVATION` variables.
  `scripts/generate_env.py` maps nested owners to these stable Compose names.
  Positive finite `cpus` quotas and positive integer `memory_reservation_mb`
  values are required. Compose requires these variables; pass `--env-file
  config/.env.shared` or use the Make targets. Memory reservations use Docker's
  `m` unit (MiB) and are soft, not hard limits or preallocated memory.
  Recreate containers with `make up-detached` to apply changed values, between
  backtests. Docker Desktop's overall CPU/RAM/swap budget is configured separately
  on the host; per-service limits do not constrain image builds.
- TimescaleDB topology generates both application-facing `TIMESCALEDB_DB` /
  `TIMESCALEDB_USER` values and image-facing `POSTGRES_DB` / `POSTGRES_USER`
  aliases. The password remains only in `config/.env.secrets.db`.
- Backtester topology generates API host/port/logging values,
  `BACKTESTER_WORKER_POLL_INTERVAL_SECONDS`, and
  `BACKTESTER_MAX_SWEEP_CANDIDATE_COUNT`; the defaults are one second and 1,000
  raw candidates respectively. It also generates
  `BACKTESTER_WORKER_HEARTBEAT_INTERVAL_SECONDS` (default five seconds) and
  `BACKTESTER_WORKER_STALE_AFTER_SECONDS` (default 30 seconds); the latter must
  exceed the former.
- Frontend proxy targets are generated from service topology as
  `VITE_PROXY_DATA_ACCESSOR_TARGET`, `VITE_PROXY_BACKTESTER_TARGET`, and
  `VITE_PROXY_INDICATOR_TARGET`.
- `backtester/cli.py` is the other direct topology reader and applies the same local
  overrides. It resolves the local
  accessor endpoint from `public.host` and
  `services.database_accessor_api.network.published_port`, with the existing
  internal-port and generated-env fallbacks. Update its lookup and CLI tests
  whenever that topology path changes.

## Change Triggers

- Add tracked non-secret settings to `topology.yaml` and `scripts/generate_env.py`
  together.
- Do not hand-edit generated env files.
- Validate port changes against `docker-compose.yml` and frontend Vite proxy env.
- If configuration ownership changes, update the relevant ADR under `docs/adr/`.

## Verification

- Config validation: `make validate-config`.
- Structure-only changes must preserve all four generated env mappings. The
  preservation fixture in `scripts/tests/fixtures/topology_environment.json`
  uses empty secret inputs; update it only when runtime values intentionally change.
- Stack-affecting host or port changes should be smoke-tested with the relevant
  Compose target.
