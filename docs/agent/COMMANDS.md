# Agent Commands

Run from the repository root. [Makefile](../../Makefile) is the command inventory
and defines each gate; [frontend/package.json](../../frontend/package.json) owns
individual frontend scripts.

## Choosing a Gate

| Scope | Command |
| --- | --- |
| Backend area | `make test <area>`; supported areas are listed in `Makefile` |
| All configured backend suites | `make test` |
| Frontend lint, types, layout, unit tests, build | `make test frontend` |
| Python lint/format and types | `./lint-python.sh` and `make typecheck-python` |
| Full implementation handoff | `make verify` |
| Config generation / validation | `make config` / `make validate-config` |
| Deployed asynchronous success/failure | `make smoke-backtester` |

`make test` excludes the frontend and opt-in live PostgreSQL checks. The async
worker requires Linux process supervision; use Compose on other hosts.

## Stack and Environments

- `make up-build` builds and starts the stack; `make up-detached` starts it in the
  background. These targets generate configuration first.
- `make migrate-db` applies pending migrations to the running Timescale container.
  For upgrades involving workers, follow [recovery and cutover](../operations/backtest-worker-recovery.md).
- `make venvs` creates environments; `make venv SERVICE=<area>` creates one.
- Direct Compose calls need `--env-file config/.env.shared`.

## Live Storage Verification

Migration integration checks against the local stack:

```sh
RUN_MIGRATION_INTEGRATION_TESTS=1 .venv/bin/python -m unittest scripts.tests.test_migrations_integration
```

Accessor execution/deletion tests opt in with
`RUN_BACKTEST_EXECUTION_INTEGRATION_TESTS=1`; batch tests use
`BACKTEST_BATCH_TEST_DATABASE_URL`. For isolated database setup and worker
interpreter requirements, see the
[acceptance procedure](../operations/backtest-workspace-v1-acceptance.md#reproduce-the-gates).
Check suite skip conditions before claiming live coverage.
