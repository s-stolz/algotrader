# Frontend readability and preservation

`npm run format` formats handwritten frontend code. `npm run format:check`
rejects unformatted equivalents, including compressed CSS and Vue attributes.
The formatter configuration owns layout settings; ESLint owns semantic checks.
`scripts/frontend-source.mjs` owns the shared source inventory for formatting and
readability. It includes application code, tests, nested scripts, and handwritten
configuration. Dependency/build/coverage directories and generated lock/inventory
files are excluded; ordinary nested source directories are included.

## Migration checks

`npm run check:readability:strict` applies the hard limits to the entire source
inventory. `scripts/source-readability.mjs` owns the limits and comment counting.
All Vue blocks, standalone CSS, scripts, and tests count. Only blank lines and
actual comment-only lines are excluded from file size. Width still includes
comments. Width exceptions cover standalone indivisible URL, regex, and unspaced
literal content; an ordinary string or attribute does not exempt surrounding
code. Wrap compressible code around an indivisible token before relying on an
exception.

During spec #17, `npm run check:readability` also reads the explicit generated
`readability-inventory.json`. Each remaining file belongs to an approved ticket.
The gate rejects new debt files, increased oversized-file counts, changed or
additional over-width lines, and resolved entries left in the inventory. Existing
width allowances match exact line contents and occurrence counts, so adding an
ordinary string or duplicating a violation cannot bypass the gate. Shrinking an
oversized file is permitted. Remove its inventory entry once all violations are
resolved. Do not regenerate the inventory to accept new debt.

`npm run check:readability:inventory` prints every current violation, including
line numbers and measured size. This is a reporting command, not a passing gate.
Ticket #30 removes staging and makes the complete strict check the normal gate.
No permanent legacy exemptions are part of this migration. `make test frontend`
already requires formatting, staged readability, tooling fixtures, lint, types,
test layout, unit tests, and a production build.

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
limits, migration debt, and valid/invalid test ownership.

## Baseline for spec #17

The baseline checkout was `3d9711faf7b5cf7e90204d9296336e513b5d5245`. Before
formatting, lint, types, layout (62 suites), and production build passed. Ten
existing file-size warnings were present. All 327 unit tests passed with a
checkout-specific temporary runner override described below. No unprotected
behavior gap requiring new application characterization tests was identified.
The pure normalization commit is `09bd181088f269e0ab7e961caaf7fae83fb939cc`.
Its 32 changed Vue templates compile to equivalent render-function ASTs; all 327
application tests pass after formatting. Existing text and behavior assertions
were preserved.

Vite's default `**/.git/**` filesystem denial prevents Vitest from loading setup
files in the Vibe worktree. The initial unmodified gate failed all suites with
`Cannot find module '/test/setup.ts'`. A temporary, untracked configuration
imports the existing Vite configuration and removes only that denial for local
checks, retaining `.env`, `.env.*`, and certificate/private-key restrictions.
It does not change production configuration. The baseline then passed all suites.
A post-format concurrent run hit Workspace timeouts; the isolated Workspace suite
(65 tests) and the complete serial suite passed unchanged. Preserve these runner
details when reproducing checks in a `.git`-hosted checkout.

Fresh populated charting and Workspace screenshots remain qualification work.
The browser connector reached an app, but its source identity could not be bound
to this checkout. Automatic approval review rejected private-source hash binding
through that external connector as unapproved sensitive egress. No image from that
unverified app is claimed as a production baseline. Before accepting visible
changes, serve an identified checkout with representative data, wait for bundled
fonts and stable chart rendering, and capture chart/history/results, creation
steps, menus/dialogs, and wide/narrow viewports. Record source identity, input data,
viewport, and reproducible navigation; compare the same states after styling.
Historical acceptance reports and the HTML prototype do not replace these images.
