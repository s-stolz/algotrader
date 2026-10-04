# Coding Conventions

Formatter, linter, and type-check configuration owns mechanical style. Follow
local module patterns; introduce an abstraction when it concentrates behavior or
shared contract knowledge.

## Python

- Service tests use `unittest` under `tests/`.
- Preserve established transport / application / domain / infrastructure seams.
- Backtester tests mirror `src/<area>/` under `tests/<area>/`. Root tests cover
  root modules and layout/import checks; `tests/test_layout.py` enforces this.

## Frontend

- Use Vue, Pinia, Vitest, and Vue Test Utils patterns already present in the area.
- Keep transport validation in `src/types/contracts.ts` or focused helpers.
- Prefer store/utility tests when behavior does not require a mounted component.
- Shared controls and theme ownership are in
  [frontend context](../../frontend/CONTEXT.md#shared-ui-and-transport).

## Boundaries and Checks

Cover changed behavior, especially endpoint/stream contracts, with tests at the
owning boundary. Follow [workflow](WORKFLOW.md) for verification and
[contract changes](CONTRACT-CHANGES.md) for producer/consumer coordination.
For topology or environment changes, read [configuration context](../../config/CONTEXT.md).
