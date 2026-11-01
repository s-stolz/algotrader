# SMA crossover numerical parity investigation

Status: deferred bug; reproduced in memory on 2026-11-01. No production fix
or persistent regression test has been applied by this investigation.

## Impact and scope

Batch and sequential SMA calculations can produce different crossover signals
from identical candles because their floating-point summation histories differ.
This can change trades, costs, and ending equity. It is a correctness issue,
not display rounding.

The remaining indicator-data, opening-range, and chart framework work can
continue independently. SMA-based performance comparisons between engines
should not be treated as validated until this issue is fixed. Its effect on
other consumers of the numerical helpers remains to be assessed.

## Reported runs

The supplied saved requests match except for engine. Both use EURUSD on
IC Trading, M1, SMA windows 5/20, quantity 1, long-and-short execution, no price
stop or profit target, 3 bps commission, and 1 bp slippage. The interval is
`[1790899200000, 1793491200000)` and initial capital is 10000.

| Engine | Run ID | Executable bars | Closed trades | Ending equity derived from return |
| --- | --- | ---: | ---: | ---: |
| Vectorized | `571c369c-6049-4c7b-a9a5-0f6b2d358821` | 29817 | 1831 | 9998.389585971449 |
| Event-driven | `0c0e7347-f10f-4101-a69e-4cde274dc8a3` | 29817 | 1823 | 9998.397065979456 |

The numerical bug below is confirmed independently. It is a likely explanation
for this discrepancy, but the eight extra trades have not been individually
attributed: the original candles and fills were unavailable to this side-thread
investigation. Equal bar counts do not establish identical candle contents.

## Reproduction

Run from the repository root. This harness uses synthetic data, disables result
persistence and bytecode writes, and does not change source files.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backtester/src backtester/.venv/bin/python -B - <<'PY'
from dataclasses import replace
import numpy as np
import pandas as pd
from app.backtest_runner import run_backtest
from domain.enums import BacktestEngine
from domain.types import BacktestRequest, ExecutionConfig, StrategyConfig
from strategies.examples.sma_crossover import build_sma_crossover_strategy

bars = pd.DataFrame(dict(
    timestamp_ms=np.arange(36) * 60000,
    symbol="EURUSD", open=1.1, high=1.1, low=1.1, close=1.1, volume=1.0,
))
request = BacktestRequest(
    symbols=["EURUSD"], timeframe="M1", start_ms=1200000, end_ms=2160000,
    initial_capital=10000,
    strategy=StrategyConfig(strategy_id="sma_crossover"),
    execution=ExecutionConfig(commission_bps=3, slippage_bps=1),
    persist_result=False,
)
strategy = build_sma_crossover_strategy(fast_window=5, slow_window=20)
results = [
    run_backtest(request=replace(request, engine=engine), bars=bars, strategy=strategy)
    for engine in BacktestEngine
]
for result in results:
    print(result.request.engine.value, len(result.trades), len(result.fills),
          result.equity_curve[-1].equity)
assert all(not result.fills for result in results), "Flat prices produced false SMA trades"
PY
```

Observed output before a fix:

```text
vectorized 1 2 9999.998679967
event_driven 0 0 10000.0
AssertionError: Flat prices produced false SMA trades
```

The same input at price 1.0 produces no trades in either engine. With 120
candles at price 1.1, vectorized produces three closed trades and event-driven
produces none.

## Isolated cause

- [rolling_mean](../../libs/indicator_engine/indicator_engine/indicators/utils.py)
  subtracts cumulative totals to obtain each window sum.
- [UpdateEngine](../../libs/indicator_engine/indicator_engine/engines/update.py)
  runs SMA on only its current warmup window; batch evaluation operates on the
  full supplied history. The summation histories therefore differ.
- [Crossover conditions](../../backtester/src/strategies/conditions.py) use strict
  comparisons. On flat 1.1 candles, batch fast-minus-slow changes from roughly
  `-2.22e-16` to `+2.22e-16`, while sequential fast-minus-slow stays zero in the
  reproduction. That sign change becomes a trade signal.

Replacing only the SMA mean function temporarily in memory with direct
per-window means eliminates the false trades in the 36-candle reproduction.
Execution, warmup, and costs were unchanged. This isolates the arithmetic as a
cause; the experimental implementation is not a selected production solution.

## Follow-up scope and acceptance criteria

Choose a numerically stable calculation with consistent batch/sequential
behavior using ordinary float64 unless measurements justify another approach.
Assess whether crossover equality also needs a small, explicitly justified
numerical tolerance; do not pick an arbitrary trading threshold to mask drift.

Avoid materializing an N-by-window-size copy of the input. Benchmark runtime and
peak memory on representative history lengths and windows. A compiled rolling
calculation can still supply arrays to the vectorized execution engine; a full
backtester architecture redesign is not a prerequisite.

Acceptance criteria:

1. Identical flat candles produce no crossover trades in either engine.
2. Genuine small crossovers remain detectable at representative FX price scales.
3. Long, quantized histories yield matching signals, fills, and trade counts
   across engines; accounting differences stay within documented numerical bounds.
4. Warmup, run-start boundaries, missing data, and calculation slicing are covered
   separately so arithmetic changes do not hide timing or data differences.
5. Recheck the original run inputs and identify the first divergent signal/fill.
6. Record speed and peak-memory measurements before selecting the solution;
   do not require higher precision or an N-by-window-size allocation by default.

## Ticket draft

**Title:** Fix numerical parity of SMA crossover signals across backtest engines

Identical constant-price candles can produce false SMA crossover trades in the
vectorized engine while the event-driven engine produces none. Batch cumulative
sums and sequential window calculations round differently near equal SMA values.
Select a stable, memory-bounded float64 calculation, define numerical equality
if needed, and add regression coverage for flat prices, genuine small crossovers,
and long histories. Verify signal/trade parity and benchmark runtime and peak
memory. See this investigation for the reproduction and reported run IDs.
