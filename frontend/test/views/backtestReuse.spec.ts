import { describe, expect, it } from 'vitest';

import type { BacktestBatch, BacktestRun } from '@/types/backtesterContracts';
import { reuseBatch, reuseStandalone } from '@/views/backtestReuse';

const request = {
  symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M15',
  start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000,
  engine: 'event_driven', data_granularity: 'bar', initial_capital: 25_000,
  strategy: { strategy_id: 'sma', strategy_version: 2,
    parameters: { fast: 3, slow: 10 } },
  execution: { signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
    allow_partial_fills: false, allowed_directions: 'short_only',
    trade_accounting_policy: 'average_cost', gap_policy: 'skip',
    intrabar_exit_policy: 'conservative', commission_bps: 1, slippage_bps: 2 },
  persist_result: true, run_metadata: { name: 'Original' },
} as const;

describe('saved configuration reuse', () => {
  it('copies a standalone request without retaining result history or assigning legacy identity', () => {
    const run = { run_id: 'old', request_schema_version: 2, request,
      status: 'succeeded' } as unknown as BacktestRun;
    const before = structuredClone(run);
    const reuse = reuseStandalone(run);
    expect(reuse.source.strategyVersion).toBeNull();
    expect(reuse.request).toMatchObject({ timeframe: 'M15', initial_capital: 25_000,
      strategy: { parameters: { fast: 3, slow: 10 } },
      execution: { allowed_directions: 'short_only' }, run_metadata: null });
    reuse.request.strategy.parameters.fast = 99;
    expect(run).toEqual(before);
  });

  it('copies accepted ordered selections and ranges instead of resolved members', () => {
    const batch = {
      batch_id: 'saved-batch', strategy_id: 'sma', strategy_version: 2,
      accepted_definition: { shared_request: { ...request, symbols: [], exchange: null,
        timeframe: 'M1', strategy: { strategy_id: 'sma', strategy_version: 2,
          parameters: {} } },
        normalized_selections: {
          markets: [{ symbol_id: 2, symbol: 'GBPUSD', exchange: 'FX' },
            { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
          timeframes: ['H1', 'M15'], allowed_directions: ['short_only', 'long_only'],
          parameters: {
            fast: { mode: 'range', values: [3, 5, 7], range: { start: 3, stop: 7, step: 2 } },
            slow: { mode: 'default', values: [10] },
          },
        } },
      strategy_metadata: { strategy_id: 'sma', strategy_version: 2, display_name: 'SMA',
        parameters: [{ name: 'fast', type: 'int', required: false, nullable: false, default: 3 },
          { name: 'slow', type: 'int', required: false, nullable: false, default: 10 }] },
    } as unknown as BacktestBatch;
    const before = structuredClone(batch);
    const reuse = reuseBatch(batch);
    expect(reuse.sweep.marketIds).toEqual([2, 1]);
    expect(reuse.sweep.timeframes).toEqual(['H1', 'M15']);
    expect(reuse.sweep.allowedDirections).toEqual(['short_only', 'long_only']);
    expect(reuse.sweep.parameters.fast).toMatchObject({ mode: 'range', rangeStart: 3,
      rangeStop: 7, rangeStep: 2 });
    expect(reuse.source.defaultedParameters).toEqual(['slow']);
    reuse.sweep.marketIds.reverse();
    expect(batch).toEqual(before);
  });
});
