# Configuration Context

Centralized non-secret topology plus generated runtime environment files.

## Owned Interfaces

- Tracked non-secret topology in `topology.yaml`.
- Gitignored local secret input and generated runtime env outputs.
- Validation and generation behavior in `scripts/generate_env.py`.
- Docker Compose and local process environment contracts.

## Key Files

- `topology.yaml`: tracked shared topology for hosts, ports, logging, Redis,
  TimescaleDB, broker limits, and ingestion/webserver knobs.
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
