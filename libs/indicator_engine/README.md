# Indicator Engine

A lightweight, NumPy-first indicator library designed for fast batch calculations and streaming updates.

This library is used by services such as `indicator-api` and is intended to scale to backtests, live
indicator streams, and ML feature generation.

## Goals

- Vectorized, multi-asset, multi-parameter indicator evaluation.
- Streaming updates with bounded memory via rolling history.
- Strict, aligned time index per timeframe.
- Deterministic parameter grids for reproducible research.
- Separation of compute metadata (library) and UI metadata (API/frontend).

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

## Indicators Included

- `sma`
- `rsi`
- `macd`
- `bbands`
- `currency_strength` (fixed FX inputs: EURUSD, USDJPY, USDCHF, GBPUSD, AUDUSD, USDCAD, NZDUSD)

## NaN Propagation

The library intentionally propagates NaN values and does not forward-fill or interpolate.
This keeps data integrity explicit and reproducible.
