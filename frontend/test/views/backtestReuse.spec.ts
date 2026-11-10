import { describe, expect, it } from 'vitest';

import type { Backtest, BacktestRun } from '@/types/backtesterContracts';
import { reuseBacktest, reuseRun } from '@/views/backtestReuse';

const request = {
  symbols: ['EURUSD'],
  exchange: 'FX',
  timeframe: 'M15',
  start_ms: 1_714_521_600_000,
  end_ms: 1_714_608_000_000,
  engine: 'event_driven',
  data_granularity: 'bar',
  initial_capital: 25_000,
  strategy: {
    strategy_id: 'sma',
    strategy_version: 2,
    parameters: { fast: 3, slow: 10 },
  },
  execution: {
    signal_timing: 'close',
    fill_timing: 'next_open',
    price_source: 'open',
    allow_partial_fills: false,
    allowed_directions: 'short_only',
    trade_accounting_policy: 'average_cost',
    gap_policy: 'skip',
    intrabar_exit_policy: 'conservative',
    commission_bps: 1,
    slippage_bps: 2,
    max_entries_per_day: 2,
    daily_schedule: {
      entry_start_minute_utc: 60,
      last_entry_minute_utc: 120,
      exit_minute_utc: 180,
    },
  },
  run_metadata: { name: 'Original' },
} as const;

const copyNames = [
  [undefined, ''],
  [null, ''],
  ['', ''],
  ['Original', 'Original (copy)'],
  ['a'.repeat(113), 'a'.repeat(113) + ' (copy)'],
  ['😀'.repeat(120), '😀'.repeat(113) + ' (copy)'],
] as const;

describe('saved configuration reuse', () => {
  it('uses saved IDs and current names with explicit exchange matching', () => {
    const run = {
      run_id: 'saved',
      request_schema_version: 3,
      request: structuredClone(request),
    } as unknown as BacktestRun;
    const markets = [
      {
        symbol_id: 1,
        symbol: 'RENAMED',
        exchange: 'NEW',
      },
    ];
    expect(reuseRun(run, markets).selections.marketIds).toEqual([]);
    run.request.exchange = null;
    expect(reuseRun(run, markets).selections.marketIds).toEqual([]);
    run.request.instrument = {
      symbol_id: 1,
      settlement_currency: 'USD',
      contract_multiplier: 1,
      minimum_quantity: 1,
      quantity_step: 1,
      min_move: 0.01,
    };
    expect(reuseRun(run, markets).selections.marketIds).toEqual([1]);
    run.request.instrument.symbol_id = 2;
    run.request.exchange = 'FX';
    expect(reuseRun(run, markets).selections.marketIds).toEqual([]);
  });

  it('copies a Run into an independent fixed-parameter draft', () => {
    const run = {
      run_id: 'old',
      backtest_id: 'parent',
      run_ordinal: 0,
      request_schema_version: 3,
      request,
      status: 'succeeded',
    } as unknown as BacktestRun;
    const before = structuredClone(run);
    const reuse = reuseRun(run, [
      { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' },
    ]);
    expect(reuse.source.strategyVersion).toBe(2);
    expect(reuse.selections.dailySchedule).toEqual({
      enabled: true,
      candidates: [request.execution.daily_schedule],
    });
    expect(reuse.request).toHaveProperty('name', '');
    expect(reuse.request).toMatchObject({
      timeframe: 'M15',
      initial_capital: 25_000,
      strategy: { parameters: { fast: 3, slow: 10 } },
      execution: {
        allowed_directions: 'short_only',
        max_entries_per_day: 2,
        daily_schedule: request.execution.daily_schedule,
      },
      run_metadata: null,
    });
    reuse.request.strategy.parameters.fast = 99;
    reuse.request.execution.max_entries_per_day = 1;
    reuse.request.execution.daily_schedule!.exit_minute_utc = 240;
    expect(run).toEqual(before);
  });

  it.each(copyNames)(
    'copies a backtest name %s with accepted ordered selections and ranges',
    (name, proposed) => {
      const backtest = {
        backtest_id: 'saved-backtest',
        name,
        strategy_id: 'sma',
        strategy_version: 2,
        accepted_definition: {
          shared_request: {
            ...request,
            symbols: [],
            exchange: null,
            timeframe: 'M1',
            strategy: {
              strategy_id: 'sma',
              strategy_version: 2,
              parameters: {},
            },
          },
          normalized_selections: {
            markets: [
              { symbol_id: 2, symbol: 'GBPUSD', exchange: 'FX' },
              { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' },
            ],
            timeframes: ['H1', 'M15'],
            allowed_directions: ['short_only', 'long_only'],
            daily_schedules: [
              request.execution.daily_schedule,
              {
                entry_start_minute_utc: 360,
                last_entry_minute_utc: 600,
                exit_minute_utc: 960,
              },
            ],
            parameters: {
              fast: {
                mode: 'range',
                values: [3, 5, 7],
                range: { start: 3, stop: 7, step: 2 },
              },
              slow: { mode: 'default', values: [10] },
            },
          },
        },
        strategy_metadata: {
          strategy_id: 'sma',
          strategy_version: 2,
          display_name: 'SMA',
          parameters: [
            {
              name: 'fast',
              type: 'int',
              required: false,
              nullable: false,
              default: 3,
            },
            {
              name: 'slow',
              type: 'int',
              required: false,
              nullable: false,
              default: 10,
            },
          ],
        },
      } as unknown as Backtest;
      const before = structuredClone(backtest);
      const reuse = reuseBacktest(backtest);
      expect(reuse.request).toHaveProperty('name', proposed);
      expect(reuse.selections.marketIds).toEqual([2, 1]);
      expect(reuse.selections.timeframes).toEqual(['H1', 'M15']);
      expect(reuse.selections.allowedDirections).toEqual([
        'short_only',
        'long_only',
      ]);
      expect(reuse.selections.parameters.fast).toMatchObject({
        mode: 'range',
        rangeStart: 3,
        rangeStop: 7,
        rangeStep: 2,
      });
      expect(reuse.request.strategy.parameters.slow).toBe(10);
      expect(reuse.selections.dailySchedule).toEqual({
        enabled: true,
        candidates:
          backtest.accepted_definition.normalized_selections.daily_schedules,
      });
      reuse.selections.dailySchedule.candidates[0].exit_minute_utc = 240;
      reuse.selections.marketIds.reverse();
      expect(backtest).toEqual(before);
    },
  );
});
