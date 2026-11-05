# SMA crossover numerical parity

Status: open; reproduced on current code during the cleanup audit.

Batch and sequential SMA calculations can produce different crossover signals
from identical candles because floating-point summation histories differ.
This changes trades, costs, and ending equity. Flat prices should produce no trades.
The numerical fix is outside the legacy cleanup scope.

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

## Cause and acceptance

The batch [rolling mean](../../libs/indicator_engine/indicator_engine/indicators/utils.py)
subtracts cumulative totals; the streaming engine calculates over its warmup window.
Near equal SMAs, rounding differences cross the strict comparison boundary in
[crossover conditions](../../backtester/src/strategies/conditions.py).

A fix must prevent flat-price trades while retaining genuine small crossovers,
preserve warmup and missing-data semantics, and verify signal/fill parity over long
histories. Benchmark time and memory before selecting an approach; avoid an
N-by-window allocation or arbitrary trading tolerance to hide numerical drift.
