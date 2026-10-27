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

Use `BaseDatePicker` for creation calendars: its owned body-level target carries
the design variables and typography outside scrolling drawers. Numeric controls
remain Naive `NInputNumber` and inherit the shared Input peer theme.

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
| Backtest creation and its overlays | #29, explicit `DesignScope` |
| Root compatibility provider and legacy theme branches | #30 removal |

Do not wrap the entire root before these consumers are migrated. BasePopover
must preserve legacy typography/defaults outside the scope until its consumers
move.

The chart opts in at its toolbar, rendering area, and Indicator search boundary.
Pane overlay targets receive the derived variables explicitly because Vue
Teleports retain provider context but do not inherit their original DOM ancestry.
`BaseColorPicker` owns its teleported host and removes it with the control. Naive
exposes one radius for both color trigger and panel and no panel style hook;
the control's narrow trigger selector keeps the trigger round while the supported
theme radius keeps the panel ordinary. Preserve user-selected series colors. The final contract ticket #30 owns removing compatibility mode and checking
all consumers against the authority, including overlays and chart labels.

Chart options and measurement labels pass the UI face explicitly to canvas.
Chart rendering waits for the requested bundled face and font readiness before
creating the chart; sessions keep updating their existing stores while rendering
waits. Disposing the chart cancels that pending callback. If font loading fails,
the ordinary font stack remains the fallback so data access stays available.

Market dialogs opt in individually, preserving their existing state lifetime.
`BaseModal`, `BaseSelect`, `BaseDropdown`, and `BaseDataTable` consume that scope;
select menus and dropdown roots carry the derived CSS properties through their
teleports. The provider owns input, upload, selection, and table settings through
supported Naive themes. Unscoped callers retain the compatibility branch until
their workflow migrates.
