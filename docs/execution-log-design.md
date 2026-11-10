# Execution log implementation verdict

The accepted prototype is preserved locally on
`prototype/execution-log-docked-2026-11-10` at
`ff45507130cfb363482b08b7dce85fadccfcfa57`. No implementation issue was supplied;
this document records the design verdict and prototype reference instead.

Use a full-width bottom dock with Naive UI's resizable `NSplit`. Opening the dock
shrinks the current page while preserving its mounted state. Viewport-fixed edge
navigation exposes the page switch and Trades toggle together. Only an explicitly
selected Run exposes Trades; opening a Run on the Chart selects its log without
opening the dock. Selection is not persisted across a fresh app load.

The table groups entry/exit rows under one Trade, with shared quantity, combined
fees and net PnL. An opt-in switch includes genuinely unexecuted Orders with a
muted amber treatment and Not executed label. Internal Order identifiers stay out
of the presentation. Floating pagination has subdued idle opacity and no reserved
footer. There is no separate hide control, fills tab, or inspection search.

Production inspection uses the dedicated server-paginated execution-log endpoint,
10 records per request. Lightweight workspace Run reads omit diagnostics. Chart
activation retains the existing full artifact/diagnostics path because pending
entry overlays and saved chart indicator snapshots require it. The new paginated
inspection path does not fetch those full artifacts.

Verification uses mounted component/lifecycle tests, API boundary tests, and live
PostgreSQL pagination tests. Browser automation was unavailable in this session;
these checks do not establish a visual browser review.
