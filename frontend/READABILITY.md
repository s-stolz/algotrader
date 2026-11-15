# Frontend readability and preservation

`npm run format` formats Prettier-supported handwritten frontend code.
`npm run format:check` rejects unformatted equivalents, including compressed CSS
and Vue attributes. The formatter configuration owns layout settings; ESLint owns
semantic checks. `scripts/frontend-source.mjs` owns the complete source inventory
for hard limits: application code, tests, nested scripts, handwritten
configuration, the deployment entrypoint, Dockerfile, and ignore configuration.
Dependency/build/coverage directories, generated lockfiles, and binary assets
are excluded; ordinary nested source directories are included.

Prettier's bundled parsers cover Vue, TypeScript/JavaScript, CSS, JSON, and HTML.
Shell, Dockerfile, and ignore syntax have no bundled parser: the formatter leaves
those inputs intact, and the complete hard-limit check still measures them.
Preserve readable shell/configuration layout and check shell syntax with `sh -n`
when changing the entrypoint. No deployment input is exempt from hard limits.

## Mandatory checks

`npm run check:readability` applies the hard limits to the entire source inventory.
`scripts/source-readability.mjs` owns the limits and comment counting. All Vue
blocks, standalone CSS, scripts, configuration, and tests count. Only blank lines
and actual comment-only lines are excluded from file size; quoted text and
heredoc content still count. Width still includes comments. Width exceptions
cover standalone indivisible URL, regex, and unspaced literal content; an ordinary
string or attribute does not exempt surrounding code. Wrap compressible code
around an indivisible token before relying on an exception.

The normal gate has no migration inventory, file allowances, or higher test limit.
`npm run check:readability:inventory` reports any current violations with line
numbers and measured size; it is a diagnostic command, not a passing gate.
`make test frontend` requires formatting, complete readability, tooling fixtures,
lint, types, test layout, unit tests, and a production build.

## Behavior-specific test suites

Tests mirror their source directory under `test/`. Keep exact-name suites such as
`test/components/Chart/chartSession.spec.ts`, or use
`<source-basename>.<behavior>.spec.ts` for a cohesive observable behavior group,
such as `chartSession.history-paging.spec.ts`. The behavior suffix uses lowercase
letters, digits, and hyphens, beginning with a letter. The checked source owner
must exist in the corresponding `src/` directory. An exact match takes precedence
for source basenames that already contain a dot. Shared fixtures and helpers stay
under `test/` and need no artificial production counterpart. Preserve assertions
and state ownership when splitting suites; describe behavior rather than numbered
chunks.

Run `npm run test:tooling` for fixtures covering discovery, formatting, strict
limits, deployment inputs, and valid/invalid test ownership.

## Feature organization and preservation

The kept-alive `BacktestWorkspaceView.vue` creates the coordinator in
`src/views/workspace/useBacktestWorkspace.ts` once. It owns navigation,
selection reconciliation, and lifecycle cleanup. Its history model owns filters
and pagination; history presentation consumes that model and coordinated actions.
Request serialization and command availability live beside the coordinator.
The existing Pinia store retains creation drafts and name acknowledgement order.
Presentation sections must not recreate these owners when visibility changes.

The kept-alive View also creates its comparison model once. Inspection sections
consume the coordinator and that model; conditionally rendered tables and column
settings never recreate durable sorting, pagination, or visible-column state.
Comparison cell mapping and coordinated actions live in `workspace/comparison/`.
Replay presentation derives compatibility, errors, and chart series from the
existing analysis owner without issuing requests or owning polling.

Backtest inspection keeps a single model created by `BacktestOverview.vue`.
It owns detail generations, event subscription cleanup, command retry identities,
and name acknowledgements; progress and saved-definition/activity sections only render it.
The Backtest tests retain their exact-name suite plus command and progress behavior
groups with shared fixtures. The complete hard-limit gate covers these source owners and their suites.

Workspace suites use descriptive behavior suffixes with shared fixtures. Tests
exercise history and Run inspection through the parent Backtest, including a
single Run, event refresh, command retries, copying, and comparison state.
