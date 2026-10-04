# Agent Instructions

Read [CONTEXT.md](CONTEXT.md) for shared vocabulary and contracts, then use
[the context map](docs/CONTEXT-MAP.md) to select task-specific guidance.

- **Implementation:** read the affected area's `CONTEXT.md` before editing and
  [coding conventions](docs/agent/CODING-CONVENTIONS.md) for code or test changes.
- **Contracts:** before changing a service interface or storage contract, follow
  [contract changes](docs/agent/CONTRACT-CHANGES.md).
- **Architecture:** consult [ADRs](docs/adr/README.md) before revisiting an
  established boundary.
- **Verification:** follow [workflow](docs/agent/WORKFLOW.md); use
  [commands](docs/agent/COMMANDS.md) to select the relevant gate.

Keep real secrets in gitignored local configuration. Exclude `.venv/`,
`node_modules/`, `dist/`, `__pycache__/`, and `.ruff_cache/` from exploration unless
the task concerns generated output.
