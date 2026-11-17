# GitHub project lifecycle

When creating or updating AlgoTrader issues through Wayfinder, ticket planning, or
implementation, synchronize their membership and Status in
[AlgoTrader](https://github.com/users/s-stolz/projects/3) (owner `s-stolz`, project
number `3`). Repository: `s-stolz/algotrader`.

## Status

Labels classify work and support existing triage and execution protocols. The
project's Status field determines its board column. Read the issue, dependencies,
claim, and delivery evidence before selecting a status.

| Issue lifecycle | Status |
| --- | --- |
| New work awaiting specification, or a ticket with an open blocker | Backlog |
| Specified, unblocked, unclaimed ticket available to pick up | Ready |
| Claimed ticket actively being worked on | In progress |
| Work awaiting review or human merge under its owning workflow | In review |
| Closed issue | Done |
| Reopened issue | Reassess blockers and claim; use Backlog when uncertain |

For Wayfinder, Ready means its question can be investigated or discussed; it does
not mean implementation-ready. Claiming a decision moves it to In progress;
recording its resolution and closing it moves it to Done. Preserve the assignee
as the authoritative claim. Releasing a claim requires reassessing readiness.

A map represents the whole planning effort: Backlog before it starts, In progress
while charting or resolving decisions, and Done only when the destination is
reached and the map is closed. Preserve an open map when a child completes. Its
status does not consume or imply a child claim.

Done means the issue is closed. Preserve its closure reason: a discarded decision
is not a resolved decision, and a resolved planning ticket is not delivered
software. For implementation, follow the owning delivery workflow; Vibe tickets
remain open through spec-branch integration and await verified human PR merge.
Execution labels and the Vibe ledger remain authoritative for scheduling.

## Synchronization

1. Resolve the project and its Status field/options through GitHub; use their
   current IDs rather than storing generated IDs here.
2. Find the issue's existing project item; add it only when absent. For a new
   ticket batch, wire all dependencies before computing readiness.
3. Apply the Status mapping to the affected issue and any dependents whose
   readiness changed. Keep unrelated project fields and memberships intact.
4. Read back membership and Status. Reconcile again after closure, reopening,
   blocker changes, claim release, or resuming interrupted work.

Built-in auto-add and closed-to-Done workflows may supply these transitions;
verify their result. Report a failed board update separately from a successful
issue operation, retaining enough identity to retry without duplicating issues or
resolution comments. Existing assignees alone do not establish a live session;
preserve another session's claim and investigate stale claims before changing it.
