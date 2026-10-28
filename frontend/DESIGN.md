# Shared visual design

`src/design/tokens.ts` owns semantic colors, typography, text roles, spacing,
radii, control sizes, and overlay shadows. Use `designTokens` for programmatic
styling (including canvas labels), `designCssProperties` for CSS custom properties,
and `designThemeOverrides` for Naive UI. CSS names follow
`--design-<group>-<kebab-case-role>`, for example `--design-color-interactive`,
`--design-font-mono`, `--design-text-secondary`, and `--design-space-md`.
Change the authority rather than maintaining another palette in a feature.
Feature styles own content layout and chart geometry.

## Application and controls

`App.vue` owns one `Common/DesignScope.vue` around navigation and the kept-alive
routes. It provides the dark Naive theme and derived CSS variables without adding
layout geometry. `main.ts` also installs those variables on the document root for
body-level overlays. There is one visual policy for every workflow and shared
control; callers do not opt in through a migration flag or a nested provider.

Supported Naive themes in `src/design/naiveTheme.ts` and `creationControls.ts`
derive from the tokens. Ordinary buttons and fields are pills, `circle` buttons
remain circular, and panels use the panel radius. Use semantic financial
positive/negative roles independently from interactive selection. Feature-specific
Naive settings may retain purposeful layout geometry, such as Indicator tab gaps,
while inheriting the shared text and color policy.

Use the themed `Base*` controls in `src/components/Common/` where they centralize
visual policy or interaction behavior. Extend those surfaces instead of copying
local palettes or introducing pass-through wrappers. Prefer supported Naive theme
settings over selectors reaching into library internals. Necessary internal
selectors stay in the owning shared control with a short reason. Current cases
are table header roles, fixed-cell surfaces and row states in `BaseDataTable`,
and the color-picker trigger radius in `BaseColorPicker`.

## Typography and overlays

Ordinary text uses the bundled Tektur face. Technical IDs, code, and raw logs use
the monospace role. Root CSS uses inherited typography rather than a universal
descendant font rule, so explicit technical text and secondary roles remain
intact. Preserve tabular numeric alignment where values are compared.

Teleported content needs both Naive theme context and CSS variables. Shared
select, dropdown, popover, drawer, date-picker, and color-picker controls attach
the derived properties to their overlays or owned targets. Table pagination also
styles its real page-size menu. Drawer roots set the body font size explicitly
because they render outside the provider's DOM ancestry; descendants can still
use secondary, technical, and heading roles. Caller styles and supported theme
overrides retain their usual precedence.

`BaseDatePicker` owns a body-level target for creation calendars outside scrolling
drawers. `BaseColorPicker` owns and removes its teleported host. Pane overlay
targets receive variables explicitly because Vue Teleports retain provider
context but do not inherit their original DOM ancestry. Preserve user-selected
series colors. Numeric controls remain Naive `NInputNumber` and inherit the
shared Input peer theme.

## Canvas labels and state lifetimes

Chart options and measurement labels pass the UI face explicitly to canvas.
Chart rendering waits for the requested bundled face and font readiness before
creating the chart; sessions keep updating their existing stores while rendering
waits. Disposing the chart cancels that pending callback. If font loading fails,
the ordinary font stack remains the fallback so data access stays available.
Equity Replay uses the same readiness helper, renders the latest series after
that wait, and cancels deferred work on unmount. Stable replay run hues retain
their identity with saturation and lightness owned by chart tokens.

Keep presentation sections near their feature and reusable controls shared.
Extract pure mapping, validation, and rendering work separately from state
owners. Theme consolidation must not recreate chart sessions, Workspace models,
creation drafts, request generations, or command identities when sections hide.
See [frontend context](CONTEXT.md) for those owners and
[readability guidance](READABILITY.md) for source-associated behavior suites.

For rendered comparisons, wait for bundled fonts and stable canvas rendering.
Capture the same populated states and viewports from identified checkouts;
separate approved typography/control/color/spacing changes from regressions.
The standalone comparison prototype stays outside production and is not a
pixel-exact application baseline. Outstanding baseline evidence is recorded in
[readability guidance](READABILITY.md#baseline-for-spec-17).
