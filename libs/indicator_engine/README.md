# Indicator Engine

A lightweight, NumPy-first indicator library designed for fast batch calculations and streaming updates.

The historical and live indicator API and the backtester use this shared
computation library.

## Goals

- Vectorized, multi-asset, multi-parameter indicator evaluation.
- Streaming updates with bounded memory via rolling history.
- Strict, aligned time index per timeframe.
- Deterministic parameter grids for reproducible research.
- Separation of numerical specifications, application registration/presentation,
  API transport formatting and frontend renderers.

## Core Concepts

### BarTensor

A bar tensor is a dense, aligned array with shape:

```
(time, asset, field)
```

- `time`: aligned timestamps for all assets.
- `asset`: asset identifiers (symbol IDs or names).
- `field`: dynamic list defined by ingestion, commonly `open/high/low/close/volume`.

### Tensor (Indicator outputs)

Indicator outputs are returned as a `Tensor` with dims:

```
(time, asset, output, param)
```

All four dimensions are always present, even if some have length 1. This keeps adapters and
downstream consumers consistent.

### HistoryPolicy

Controls how much history buffers keep:

- `mode="rolling"`: keep only the last `max_rows` bars.
- `mode="unbounded"`: grow as needed (for batch research).

### InputHistory

Calculation history is separate from buffer retention and the minimum output
warmup. `IndicatorSpec.plan_history(start_ms=..., params=...)` returns the
calculation start and the number of available candles needed strictly before
that start. Fetch adapters own retrieval and trim results to the original output
interval only after calculation.

Rolling indicators request `warmup - 1` predecessors before the requested start.
Currency strength declares a UTC-day anchor with one predecessor: a noon request
needs candles from midnight and the preceding available close, not merely its
two-bar minimum warmup. This declaration does not itself fetch or validate data;
adapters must apply it and their missing-input policy.

Daily history can also declare a `SessionWindow` with an IANA timezone and a
required formation window. Parameter-dependent declarations use
`IndicatorSpec.resolve_input_history(params)`. The calculation starts at local
midnight; completeness is required only within the declared window.

The shared `adapters.history.prepare_daily_inputs` adapter builds daily candle
grids with per-source predecessor seeds and causal availability. It accepts sorted
source frames indexed by integer epoch milliseconds and aligned output timestamps.
Backtester and historical indicator API adapters use it to keep daily calculations
consistent. Seed rows are calculation-only and are marked unavailable as outputs.
Window boundaries must align with the candle timeframe. Missing required inputs
invalidate subsequent outputs for that local day; gaps outside the required
window do not invalidate completed calculations.

### Opening range

`opening_range` uses `start_time`, `end_time`, `extension_end_time` (HH:MM), and
`timezone`. Windows stay within one local day; `24:00` denotes its end. Candles
are identified by their opening timestamps: the range includes `[start, end)`.
High and low develop causally, freeze at the cutoff, and reset each local day.
`ready` becomes 1 at or after the cutoff when the range has valid formation
prices and its start candle. Before formation, bounds are zero and `ready` is 0;
consumers must check readiness and adapter availability before using a range.

Outputs also include `range_start_ms`, `range_end_ms`, and `extension_end_ms`
for rendering. Extension time is display metadata; it does not change formation
or erase frozen values. Nonexistent daylight-saving boundary times are rejected;
ambiguous boundary times use their first occurrence. The shared calculation is
registered in the engine; the historical chart catalog exposes it through a
dedicated range renderer with optional extension lines.

`IndicatorSpec.output_assets` declares aggregate output identities when they
differ from the inputs. Omit it for ordinary per-input-asset outputs. Currency
strength uses seven input pairs and returns the single output asset `FX` with
eight currency outputs.

### ParamGrid

Deterministic parameter grids for fast optimization and reproducibility:

- Parameter names are sorted before Cartesian product generation.
- Parameter order is stable, and `param_id` is deterministic.

## Quick Start (Batch)

```python
import numpy as np
import pandas as pd

from indicator_engine import run

# Run SMA directly on a DataFrame
result = run("sma", df, params={"window": 20, "source": "close"})

# If your DataFrame uses MultiIndex columns (field, asset), the output
# will keep MultiIndex columns (output, param, asset).
```

For quick one-offs you can skip manual registry/engine setup:

```python
from indicator_engine import run_batch

result = run_batch("sma", bar, params={"window": 20, "source": "close"})
```

## Streaming Updates

```python
import numpy as np
from indicator_engine import get_registry, get_update_engine, HistoryPolicy
from indicator_engine.core.params import ParamGrid

registry = get_registry()
engine = get_update_engine(
    registry=registry,
    history=HistoryPolicy(mode="rolling", max_rows=5000),
    max_delay_ms=5_000,
)

engine.register_indicator(
    indicator_id="sma",
    timeframe="M1",
    assets=["BTCUSD", "ETHUSD"],
    fields=["open", "high", "low", "close", "volume"],
    param_grid=ParamGrid({"window": [20]}),
)

# Push a new bar row (asset x field)
row = np.array([
    [101.0, 103.0, 99.0, 102.0, 42.0],
    [201.0, 203.0, 198.0, 202.0, 7.0],
])
engine.on_bar("M1", 1710000000000, row)

# Ergonomic extraction for singleton updates (single asset/output/param)
updated = engine.on_bar("M1", 1710000060000, row)
sma_latest = updated["sma"].latest_value()
```

Notes:
- Partial asset updates are supported by passing an `asset_mask`.
- Cross-asset indicators wait until all required assets arrive for the timestamp.
- Rolling eviction plus TTL prevents unbounded pending input growth.
- Currency strength accumulates incrementally across chronological complete
  basket rows, resets at UTC midnight, and replaces same-timestamp corrections.
  Seed it with the history declared above; a small rolling buffer does not reset
  the accumulated value. Indicator-api enables live subscriptions through its
  daily basket adapter, which adds source synchronization, complete daily history,
  and recovery; incremental calculation alone does not enforce those contracts.

## Indicators Included

- `sma`
- `ema`
- `opening_range`
- `rsi`
- `macd`
- `bbands`
- `currency_strength` (fixed FX inputs: EURUSD, USDJPY, USDCHF, GBPUSD, AUDUSD, USDCAD, NZDUSD)

## NaN Propagation

The library intentionally propagates NaN values and does not forward-fill or interpolate.
This keeps data integrity explicit and reproducible.

## Adding an indicator

Implement the numerical indicator under `indicator_engine/indicators/`. Its
`IndicatorSpec` owns the engine string ID, display name, parameters, outputs and
input/history requirements. Declare one descriptively named `IndicatorRegistration`
after the implementation in the same module:

```python
MY_INDICATOR_REGISTRATION = IndicatorRegistration(
    public_id=8,  # Choose an unused stable ID; never reuse a persisted ID.
    implementation=MyIndicator,
    supports_live=True,
    overlay=False,
    outputs={"value": {"type": "line", "plotOptions": {"color": "#2962ff"}}},
)
```

Import that constant by its descriptive name, without an alias, in
`indicator_engine/builtin_catalog.py` and append it to the ordered catalog list.
This declaration supplies default engine registration, public API identity and
metadata, and live-stream eligibility. No separate package export or API list is needed.
Preserve existing entry order and numeric IDs. Implementations must have a no-argument
constructor and a stable specification; each registry receives fresh instances.
Presentation keys must match spec outputs. Outputs without individual styles remain
in metadata with empty styles, supporting compound renderers such as opening range.
A new renderer type still requires a corresponding frontend renderer.

Histogram `plotOptions` may include `negativeColor` for values below zero;
`color` applies to zero and positive values. Without `negativeColor`, all bars
use `color`. The frontend maps this palette to per-point colors and merges
saved style overrides with current catalog defaults.

Live eligibility is a service capability, not `supports_update`: the live adapter
supports batch fallback, but some multi-input/history requirements are unsupported.
Declare eligibility explicitly and test the live adapter before enabling it.
Optional entry-point plugins remain computational registrations only; discovery
does not assign a public ID or expose a plugin to chart clients. See
[ADR-0009](../../docs/adr/0009-shared-indicator-registration-catalog.md).
