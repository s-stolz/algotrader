# Agent Workflow

Task routing starts in [AGENTS.md](../../AGENTS.md). This file owns verification
and documentation maintenance.

## Verification

- Run the relevant target from [commands](COMMANDS.md). Include affected consumer
  tests when an interface crosses areas.
- For Python changes, run `make typecheck-python`; repair findings as part of the
  change. Use `make verify` for the broad implementation handoff gate.
- For Markdown-only changes, check local links, referenced paths, and task
  routing. Application tests are unnecessary unless executable behavior changes.
- Report the checks run, their results, and any unverified behavior.

## Documentation Maintenance

- Root [CONTEXT.md](../../CONTEXT.md) owns vocabulary and cross-service summaries;
  focused references own larger contracts. Area contexts own local seams and
  gotchas. Link to the owner rather than copying its rules.
- Record facts that are costly to infer: ownership, invariants, rationale, and
  non-obvious failure modes. Let code, schemas, tool configuration, and directory
  listings supply inventories, defaults, and signatures.
- Give each pointer a task trigger. Keep historical plans and acceptance evidence
  explicitly historical and outside the default read path.
- For a contract change, follow [CONTRACT-CHANGES.md](CONTRACT-CHANGES.md). Update
  affected local guidance where responsibilities change, without repeating the
  shared contract in every consumer.
- Add an [ADR](../adr/README.md) for a durable trade-off whose rationale future
  changes need, rather than routine implementation or delivery progress.
