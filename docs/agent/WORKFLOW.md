# Agent Workflow

Use this as the agent-facing workflow interface. It keeps the default path small
while making deeper context available when the task needs it.

## Intake

1. Read root `CONTEXT.md` for domain vocabulary, system flow, and cross-service
   contracts.
2. Read `docs/CONTEXT-MAP.md` and choose the smallest task-specific context set.
3. For implementation work, read the nearest `<area>/CONTEXT.md` before editing.
4. For code or test edits, read `docs/agent/CODING-CONVENTIONS.md`.
5. For command selection, read `docs/agent/COMMANDS.md`.

## Contract Changes

Before changing Candle, Redis Candle, Tick, Timeframe, Indicator, WebSocket,
Market, Order, Position, Deal, storage, or runtime configuration contracts:

1. Read `docs/agent/CONTRACT-CHANGES.md`.
2. Update root `CONTEXT.md` if the cross-service contract changes.
3. Update each producer and consumer area context listed in the contract-change
   map.
4. Run the narrow verification target first, then broaden when the changed
   contract crosses multiple areas.

## Decision Checks

Read `docs/adr/README.md` before changing durable architecture, agent workflow,
configuration generation, or cross-service contract ownership. Add a new ADR when
the decision should prevent future agents from re-litigating the same question.

## Edit Loop

1. Inspect the relevant files and tests before editing.
2. Keep edits scoped to the requested module and its direct interfaces.
3. Prefer existing module names, helper APIs, and local patterns.
4. Add or update tests when behavior changes.
5. Update context docs only for durable contract, workflow, or locality knowledge.

## Verification

- Prefer the narrow command from `docs/agent/COMMANDS.md`.
- Run `make typecheck-python` when touching Python code; Pyright findings are
  part of the repair loop, not editor-only advice.
- Run broader commands when the changed interface is used by multiple areas.
- Use `make verify` as the broad final gate when a change is ready for handoff or
  CI-style validation.
- If only markdown changes, verify internal links and context-map routing instead
  of running application tests.

## Handoff

End with the files changed, the verification performed, and any remaining risk.
If verification was skipped, say why.
