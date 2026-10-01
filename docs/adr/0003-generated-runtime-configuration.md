# ADR-0003: Generate Runtime Configuration

Status: Accepted

Date: 2026-05-16

## Context

AlgoTrader runs multiple processes with shared host, port, Redis, TimescaleDB,
logging, broker, ingestion, and webserver settings. Some values are non-secret
topology while others are local secrets. Hand-editing runtime env files would
spread configuration knowledge across generated artifacts and increase the risk
of committing secrets.

## Decision

Use `config/topology.yaml` as the tracked source for non-secret topology and
`config/.env.secrets.local` as the gitignored source for local secrets. Generate
runtime env files with `scripts/generate_env.py` through `make config` or validate
them through `make validate-config`. Generated env files are not edited by hand.

## Consequences

- Configuration ownership is concentrated in `config/`.
- Docker Compose and local process env files stay reproducible.
- Secrets remain outside tracked files.
- Adding a new tracked setting requires updating `topology.yaml`,
  `scripts/generate_env.py`, and `config/CONTEXT.md` together.

## References

- `config/CONTEXT.md`
- `config/topology.schema.md`
- `scripts/generate_env.py`
- `README.md`

## Machine-specific overrides (2026-10-01)

Non-secret shared defaults remain tracked in `config/topology.yaml`. An optional
`config/topology.local.yaml`, ignored by Git, overrides known fields recursively
before validation and environment generation. Explicit null values replace defaults;
omitted fields retain them. A tracked example documents the local format. The
backtester CLI applies these overrides when reading topology directly. This lets
local and server clones use different tuning without modifying tracked defaults.
