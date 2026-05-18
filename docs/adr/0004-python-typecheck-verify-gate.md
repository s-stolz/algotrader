# ADR-0004: Python Typecheck Verify Gate

Status: Accepted

Date: 2026-05-17

## Context

Python editor diagnostics from Pylance/Pyright were catching defects that the
agent-facing verification flow could not see. Ruff and Black remain the lint and
format tools, but they do not check optional-member access, incompatible test
doubles, or typed service boundary mismatches.

## Decision

Pyright is a root development dependency and a strict Python verification gate.
Agents and CI-style workflows should run `make typecheck-python` for Python type
checks and `make verify` for the broad repository gate. The project does not keep
a Pyright baseline or allowlist for existing errors.

## Consequences

- Agent loops can see and repair Pyright failures instead of leaving them as
  local editor-only diagnostics.
- Test code is included in type checking, so fakes and direct route calls must
  match the contracts they exercise.
- Dynamic third-party APIs may need focused local stubs when their generated
  packages do not expose usable type information.

## References

- `scripts/typecheck_python.sh`
- `docs/agent/COMMANDS.md`
- `docs/agent/WORKFLOW.md`
