# Backtest navigation prototype

Question: how should users switch between Chart and Backtests without searching among unrelated header actions?

Run from the repository root: `npm --prefix frontend run prototype:navigation`.
Local services should already be running (`make up`). Open http://127.0.0.1:5174/backtests?variant=A.

- A — Workspace tabs: persistent destinations above both screens. Recommended starting point for two workspaces.
- B — Navigation rail: persistent destinations at the left. Useful if more workspaces are added; costs horizontal space.
- C — Adjacent screens: Chart on the left, Backtests on the right, with directional entrance animation and visible edge buttons that expand on hover. Respects reduced motion.

Use the floating arrows or keyboard Left/Right to compare. Input fields retain their arrow keys. The URL preserves the variant and current route on reload. The real memory router, kept-alive pages, reads, tables, and five-second history polling remain in use.

Create Backtest keeps the upper-right position and opens a disposable preview drawer. Refresh becomes Check now beside the data status, or Retry now after a history read error. The dedicated prototype server blocks API writes; existing destructive actions cannot change saved history there. Use the dedicated command when evaluating this prototype.

Verdict: pending user comparison. No variant has been validated or promoted. The initial recommendation is A, with the lower-priority refresh placement shared by all variants. Navigation and data actions should have distinct locations.

Primary source branch: `prototype/backtest-navigation`. No implementation issue was supplied; attach this branch to the eventual implementation issue. Keep this throwaway code off the production branch and rewrite the selected design for production after validation.
