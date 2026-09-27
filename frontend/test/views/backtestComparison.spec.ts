import { describe, expect, it } from 'vitest';
import type { BacktestRun } from '@/types/backtesterContracts';
import { compareRuns, differingSettings } from '@/views/backtestComparison';

function savedRun(id: string, ordinal: number): BacktestRun {
  return {
    run_id: id, batch_id: 'batch', member_ordinal: ordinal, status: 'succeeded',
    submitted_at_ms: 1_780_000_000_000, request_schema_version: 3,
    request: {
      symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M15',
      start_ms: 1_700_000_000_000, end_ms: 1_700_086_400_000,
      engine: 'event_driven', data_granularity: 'bar', initial_capital: 10000,
      strategy: { strategy_id: 'sma', strategy_version: 1, parameters: { fast: 10 } },
      execution: { signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
        allow_partial_fills: false, allowed_directions: 'long_and_short',
        trade_accounting_policy: 'average_cost', gap_policy: 'skip',
        intrabar_exit_policy: 'conservative', commission_bps: 1, slippage_bps: 0.5 },
      persist_result: true,
    },
    metrics: { total_return_pct: 2, max_drawdown_pct: -3 },
  };
}

describe('within-batch comparison', () => {
  it('reports each material difference without ranking the runs', () => {
    const first = savedRun('one', 0);
    const second = savedRun('two', 1);
    second.request = { ...second.request, symbols: ['GBPUSD'], timeframe: 'H1',
      start_ms: first.request.start_ms + 1000, initial_capital: 20000,
      engine: 'vectorized', strategy: { ...first.request.strategy, strategy_version: 2 },
      execution: { ...first.request.execution, commission_bps: 2,
        allowed_directions: 'long_only' } };
    expect(differingSettings([first, second])).toEqual([
      'Market', 'Timeframe', 'dates', 'strategy/version', 'Initial capital',
      'engine', 'costs', 'Allowed Directions',
    ]);
    expect(differingSettings([first])).toEqual([]);
  });

  it('sorts ties by immutable ordinal and then run ID', () => {
    const rows = [savedRun('last', 2), savedRun('first', 0), savedRun('middle', 1)];
    expect([...rows].sort((a, b) => compareRuns(a, b, 'return'))
      .map((run) => run.run_id)).toEqual(['first', 'middle', 'last']);
    expect([...rows].sort((a, b) => compareRuns(a, b, 'ordinal'))
      .map((run) => run.run_id)).toEqual(['first', 'middle', 'last']);
  });
});
