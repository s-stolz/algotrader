# Architecture Decision Records

Use ADRs for durable decisions that future agents should not re-litigate during
normal implementation work. Keep each ADR small and focused on one decision.

## Index

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-layered-agent-context.md) | Accepted | Layer agent context by read cost and task relevance. |
| [0002](0002-root-context-owns-cross-service-contracts.md) | Accepted | Root `CONTEXT.md` owns cross-service contract summaries. |
| [0003](0003-generated-runtime-configuration.md) | Accepted | Runtime env files are generated from tracked topology and local secrets. |
| [0004](0004-python-typecheck-verify-gate.md) | Accepted | Python Pyright checks are a strict verify gate. |

## When To Add An ADR

Add an ADR when a decision:

- changes a durable module interface or seam,
- constrains future implementation choices,
- explains why an obvious alternative should not be reintroduced, or
- affects multiple areas of the repository.

Do not add an ADR for temporary delivery sequencing, routine implementation
details, or a decision already captured by executable tests and local context.

## Template

Use [TEMPLATE.md](TEMPLATE.md) for new ADRs.
