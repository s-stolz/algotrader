# Shared visual design

`src/design/tokens.ts` owns semantic colors, typography, text roles, spacing,
radii, control sizes, and overlay shadows. Use `designTokens` for programmatic
styling (including canvas labels), `designCssProperties` for CSS custom properties,
and `designThemeOverrides` for Naive UI. CSS names follow
`--design-<group>-<kebab-case-role>`, for example `--design-color-interactive`,
`--design-font-mono`, `--design-text-secondary`, and `--design-space-md`.
Change the authority rather than maintaining another palette in a feature.
Feature styles own content layout and chart geometry.

Wrap a migrated workflow in `Common/DesignScope.vue`. It provides the dark Naive
theme and derived CSS variables without adding layout geometry. Existing Naive
controls consume supported theme settings directly: ordinary buttons are pills,
`circle` buttons remain circular, and panels use the panel radius. Use semantic
financial positive/negative roles independently from interactive selection.
Technical IDs, code, and raw logs use the monospace role; ordinary text uses the
bundled Tektur face. Wait for `document.fonts.ready` before rendered comparisons
or canvas text measurement.

Teleported content needs both Naive theme context and CSS variables. Shared
controls that own overlays use `useDesignScope()` to select migrated defaults
and attach `designCssProperties` to their teleported root. Keep any necessary
library-internal selector override in its owning Base control, with a reason;
prefer supported theme settings first.

## Temporary compatibility boundary

Spec #17 expands the new theme only after each workflow's structural work.
The root `App.vue` dark provider remains the compatibility default. Absence of a
`DesignScope` is an explicit legacy mode; it must not silently opt into the new
Naive overrides. Existing shared semantic CSS aliases retain their original
values while deriving from the authority. Old control-local literals remain
migration work, not a second theme to extend.

| Consumer | Scope / migration owner |
| --- | --- |
| Workspace edge navigation and Timeframe picker | #25, explicit `DesignScope` |
| Chart workflow, Indicator controls, canvas labels | #26 |
| Market dialogs and their controls | #27, explicit `DesignScope` |
| Backtest Workspace history/results and overlays | #28 |
| Backtest creation and its overlays | #29 |
| Root compatibility provider and legacy theme branches | #30 removal |

Do not wrap the entire root before these consumers are migrated. BasePopover
must preserve legacy typography/defaults outside the scope until its consumers
move. The final contract ticket #30 owns removing compatibility mode and checking
all consumers against the authority, including overlays and chart labels.

Market dialogs opt in individually, preserving their existing state lifetime.
`BaseModal`, `BaseSelect`, `BaseDropdown`, and `BaseDataTable` consume that scope;
select menus and dropdown roots carry the derived CSS properties through their
teleports. The provider owns input, upload, selection, and table settings through
supported Naive themes. Unscoped callers retain the compatibility branch until
their workflow migrates.
