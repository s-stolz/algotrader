# ADR-0001: Layer Agent Context By Read Cost

Status: Accepted

Date: 2026-05-16

## Context

AlgoTrader has many modules and cross-service contracts. Agents need enough
context to preserve Candle, Redis stream, Timeframe, storage, and WebSocket
interfaces, but reading every markdown file and long reference doc by default
wastes context and increases the chance of acting on stale detail.

## Decision

Keep the agent context interface layered:

- `AGENTS.md` stays short because many agents auto-load it.
- Root `CONTEXT.md` provides canonical domain vocabulary, system flow, and
  cross-service contract summaries.
- `docs/CONTEXT-MAP.md` routes tasks to the smallest area context set.
- Each `<area>/CONTEXT.md` owns durable local interface and locality knowledge.
- `docs/agent/WORKFLOW.md`, `docs/agent/COMMANDS.md`,
  `docs/agent/CODING-CONVENTIONS.md`, and `docs/agent/CONTRACT-CHANGES.md`
  hold workflow details that should not inflate `AGENTS.md`.

## Consequences

- Agents get high leverage from a small bootstrap.
- Durable context updates have clearer locality.
- Contributors must keep area contexts accurate when local interfaces change.
- Long README and design docs remain reference material, not the default agent
  read path.

## References

- `AGENTS.md`
- `CONTEXT.md`
- `docs/CONTEXT-MAP.md`
- `docs/agent/WORKFLOW.md`
