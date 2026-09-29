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
- `docker_resources` configures every Compose service by its Compose name.
  Positive finite `cpus` quotas and positive integer `memory_reservation_mb`
  values generate `COMPOSE_<SERVICE>_CPUS` and
  `COMPOSE_<SERVICE>_MEMORY_RESERVATION` in `.env.shared` (hyphens become
  underscores). Compose requires these variables; pass `--env-file
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

## Change Triggers

- Add tracked non-secret settings to `topology.yaml` and `scripts/generate_env.py`
  together.
- Do not hand-edit generated env files.
- Validate port changes against `docker-compose.yml` and frontend Vite proxy env.
- If configuration ownership changes, update the relevant ADR under `docs/adr/`.

## Verification

- Config validation: `make validate-config`.
- Stack-affecting host or port changes should be smoke-tested with the relevant
  Compose target.
