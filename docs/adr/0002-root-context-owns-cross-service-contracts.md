# ADR-0002: Root Context Owns Cross-Service Contracts

Status: Accepted

Date: 2026-05-16

## Context

Several contracts cross multiple modules: Candle fields, Redis Candle fields,
Tick fields, Timeframe support, Indicator streams, Market identity, WebSocket
messages, and Timescale storage semantics. If these contracts are described only
inside producer or consumer docs, agents must infer the full interface by reading
many files.

## Decision

Root `CONTEXT.md` is the canonical summary for cross-service contracts. Area
contexts own local details and must be updated when their producer or consumer
interface changes. `docs/agent/CONTRACT-CHANGES.md` maps each contract to the
contexts and verification targets that should be inspected.

## Consequences

- Contract knowledge has one primary summary and a small routing interface.
- Producer and consumer context updates become part of the contract-change
  workflow.
- Root `CONTEXT.md` must stay concise; implementation details belong in area
  contexts or reference docs.
- If a contract grows beyond a concise summary, add a focused contract reference
  and link it from root `CONTEXT.md`.

## References

- `CONTEXT.md`
- `docs/agent/CONTRACT-CHANGES.md`
- `docs/CONTEXT-MAP.md`
