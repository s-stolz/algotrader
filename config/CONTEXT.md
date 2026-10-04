# Configuration Context

`topology.yaml` owns tracked non-secret settings. Gitignored
`topology.local.yaml` overrides machine-specific values; `.env.secrets.local`
holds local secrets. Use their checked-in examples for initial setup.

## Generation and Consumers

- `scripts/generate_env.py` validates and generates runtime env files. Edit the
  inputs, then run `make config`; generated outputs remain gitignored.
- Local overrides recursively merge defaults; explicit null replaces a default,
  and unknown keys are rejected. Exact paths and supported value shapes live in
  [topology.schema.md](topology.schema.md).
- Docker Compose needs generated shared settings plus service-specific secret
  files. Direct calls require `--env-file config/.env.shared`; Make stack targets
  handle this. Database passwords stay in the database secret file.
- `backtester/cli.py` also reads topology and local overrides. Changes to accessor
  endpoint paths must update its lookup and CLI tests alongside the generator.
- Preserve stable generated env names when restructuring topology, including
  Compose resource names and frontend Vite proxy targets.
- Resource memory reservations are soft MiB reservations, not hard limits. Apply
  changed resources by recreating containers between backtests. Docker Desktop's
  host resource budget and image-build resources are separate.

## History and Worker Settings

Ingestion selects exactly one of `lookback_days` or quoted UTC `start_date`.
Changing the boundary affects future ingestion; it does not delete stored history
or fill older history before an existing latest candle. Read
[ingestion context](../ingestion-service/CONTEXT.md) for recovery semantics.

Backtester heartbeat stale threshold must exceed its heartbeat interval. Polling,
heartbeat, and sweep-limit defaults belong to topology. Heartbeat configuration
changes availability reporting, never execution-slot ownership.

## Verification

Update tracked settings, generator, and schema reference together. Run
`make validate-config`; validate port changes against Compose and frontend proxy
consumers, then smoke-test affected services.

Structure-only changes preserve all four generated env mappings. The fixture at
`scripts/tests/fixtures/topology_environment.json` uses empty secrets; update it
only when runtime values intentionally change. Configuration ownership rationale
is in [ADR-0003](../docs/adr/0003-generated-runtime-configuration.md).
