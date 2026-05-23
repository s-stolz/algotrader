# Coding Conventions

Use this file when editing code or tests. Prefer executable tool config over
restating generic language style.

## General

- Keep edits scoped to the task and the area context.
- Prefer existing patterns, module names, and helper APIs.
- Follow configured formatters and linters, especially root/service
  `pyproject.toml` files and `frontend/eslint.config.mjs`.
- Do not introduce a new abstraction unless it concentrates real behavior or
  removes repeated contract knowledge.
- Do not commit generated files, local env files, caches, or vendored artifacts.

## Python Services

- Prefer service-local `unittest` tests under `tests/`.
- Follow the established service layout where it exists:
  - `api/` for transport routes and request/response helpers.
  - `application/` for use-case modules.
  - `domain/` for value objects and models.
  - `infrastructure/` for concrete adapters.

## Vue and TypeScript

- Follow existing Vue, Pinia, and test utility patterns in `frontend/src/`.
- Keep API validation in `frontend/src/types/contracts.ts` or focused helpers.
- Prefer store or utility tests for behavior that can be tested without mounting
  a large Vue component.

## Tests

- Add tests where behavior changes, especially cross-service contracts.
- Run the narrow relevant target from `docs/agent/COMMANDS.md`; broaden when the
  blast radius crosses services.
- Add API contract or integration tests for new endpoints and stream behavior.
- Backtester tests mirror the first-level `backtester/src/` folders under
  `backtester/tests/`. Do not put source-area tests directly in
  `backtester/tests/`; the backtester layout guard fails those files.

## Contracts

- Do not redefine cross-service timestamp, Redis, candle, or storage contracts
  here. Use `CONTEXT.md` as the canonical summary.
- When a contract changes, use `docs/agent/CONTRACT-CHANGES.md` to identify the
  affected producer and consumer context files.

## Security And Configuration

- Keep real secrets in gitignored local files only.
- Use `config/topology.yaml` for tracked non-secret topology.
- Use `config/.env.secrets.local` for local secrets; it is gitignored.
- Generated env files are gitignored and produced by `python scripts/generate_env.py`.
- Validate port or healthcheck changes against `docker-compose.yml`.
