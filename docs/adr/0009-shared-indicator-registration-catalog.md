# ADR-0009: Shared indicator application registrations

Status: Accepted

Date: 2026-11-05

## Context

Built-in indicators were independently registered in engine defaults, public API
ID mappings, chart metadata and live-stream exclusions. Adding an indicator could
leave these lists inconsistent. Public numeric IDs are persisted by chart clients;
they cannot depend on engine registration order or plugin discovery.

## Decision

The shared indicator-engine package owns an application composition catalog,
separate from its numerical core. Each built-in registration declares an explicit
public ID, implementation class, live-stream eligibility and framework-neutral
chart descriptors. Each declaration lives beside its implementation class as a
descriptively named constant; the central catalog imports those names without
aliases and assembles them in public order.
Engine defaults and indicator-api consume that same catalog. Numerical specs still
own engine IDs, names, parameters, outputs and history requirements; the API owns
transport formatting and frontend owns renderer implementations.

Keep optional entry-point discovery in the computational registry. Discovery does
not publish plugins in the public catalog. Live eligibility remains explicit and
independent of incremental-update support because the live adapter can use batch
fallback but cannot yet provide every indicator's input/history requirements.

## Consequences

- Adding an implementation with its registration declaration and including that
  constant in the central catalog makes it available to engine defaults, public
  catalog/metadata and live policy. Existing renderers
  need no frontend change; a novel renderer still needs explicit frontend work.
- Shared packaging now includes presentation configuration. This accepts modest
  application metadata in the composition layer to avoid a second service-owned
  registration list. Declarations live with their indicator for locality, while
  numerical computation and engine core remain independent of presentation.
- Duplicate public/engine IDs and invalid presentation outputs fail during catalog
  construction. Missing output styles remain valid for fields consumed together
  by a compound renderer, such as opening range.
- Existing public numeric IDs must never be reassigned when entries are removed.

## References

- [Indicator engine usage](../../libs/indicator_engine/README.md)
- [Indicator API context](../../indicator-api/CONTEXT.md)
