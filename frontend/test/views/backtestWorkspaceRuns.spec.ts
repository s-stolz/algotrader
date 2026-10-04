import { describe, expect, it } from 'vitest';

import type { BacktestRun } from '@/types/backtesterContracts';
import {
  compareHistoryRuns, displayWinRate, formatMagnitude, formatSigned, runMarket, runName,
  strategyVersion,
} from '@/views/backtestWorkspaceRuns';

function run(id: string, overrides: Partial<BacktestRun> = {}): BacktestRun {
  return {
    run_id: id,
    status: 'succeeded',
    submitted_at_ms: 1000,
    request_schema_version: 2,
    request: {
      symbols: ['EURUSD'],
      exchange: 'FX',
      timeframe: 'M5',
      start_ms: 1000,
      end_ms: 2000,
      engine: 'event_driven',
      data_granularity: 'bar',
      initial_capital: 10000,
      strategy: { strategy_id: 'sma', parameters: {} },
      execution: {
        signal_timing: 'close',
        fill_timing: 'next_open',
        price_source: 'open',
        allow_partial_fills: false,
        allowed_directions: 'long_only',
        trade_accounting_policy: 'average_cost',
        gap_policy: 'skip',
        intrabar_exit_policy: 'conservative',
        commission_bps: 0,
        slippage_bps: 0,
      },
      persist_result: true,
    },
    result_schema_version: 3,
    metrics: null,
    ...overrides,
  };
}

describe('saved Backtest Run presentation', () => {
  it('uses recorded names and versions only when present', () => {
    const legacy = run('legacy');
    expect(runName(legacy)).toBe('Unnamed standalone run');
    expect(strategyVersion(legacy)).toBe('Version unavailable');
    expect(runMarket(legacy)).toBe('FX:EURUSD');

    const named = run('named', {
      name: 'Breakout baseline',
      request: {
        ...legacy.request,
        run_metadata: { name: 'Ignored legacy metadata' },
        strategy: { ...legacy.request.strategy, strategy_version: 4 },
      },
    });
    expect(runName(named)).toBe('Breakout baseline');
    expect(strategyVersion(named)).toBe('v4');
  });

  it('sorts dates and Timeframe durations numerically with name and identity ties', () => {
    const base = run('b', { request: { ...run('x').request, timeframe: 'H1' } });
    const short = run('a', { request: { ...base.request, timeframe: 'M15' } });
    expect(compareHistoryRuns(short, base, 'timeframe')).toBeLessThan(0);
    expect(compareHistoryRuns(base, short, 'timeframe')).toBeGreaterThan(0);

    const newer = run('z', { request: { ...base.request, start_ms: 10000 } });
    expect(compareHistoryRuns(base, newer, 'start')).toBeLessThan(0);

    const sameNameA = run('run-2', {
      name: 'Same',
    });
    const sameNameB = run('run-10', {
      name: 'Same',
    });
    expect(compareHistoryRuns(sameNameA, sameNameB, 'status')).toBeLessThan(0);
    expect(compareHistoryRuns(sameNameB, sameNameA, 'status')).toBeGreaterThan(0);
  });

  it('keeps signed saved values and separates zero trades from missing results', () => {
    const noTrades = run('none', {
      metrics: { long_trade_count: 0, long_win_rate_pct: 0, long_realized_pnl: 0 },
    });
    expect(displayWinRate(noTrades, 'long')).toBe('No trades');
    expect(displayWinRate(run('missing'), 'long')).toBe('—');
    expect(formatSigned(-1.25, '%')).toBe('-1.25%');
    expect(formatSigned(1.25, '%')).toBe('+1.25%');
    expect(formatSigned(0)).toBe('0');
  });

  it.each(['%', ''])('preserves nonzero values near the rounding boundary with suffix "%s"', (suffix) => {
    for (const [value, expected] of [
      [-0.005001, '-0.01'],
      [-0.005, '-0.01'],
      [-0.004999, '-0.004999'],
      [-0.004, '-0.004'],
      [-Number.MIN_VALUE, '-5e-324'],
      [0, '0'],
      [-0, '0'],
      [Number.MIN_VALUE, '+5e-324'],
      [0.004, '+0.004'],
      [0.004999, '+0.004999'],
      [0.005, '+0.01'],
      [0.005001, '+0.01'],
    ] as const) {
      expect(formatSigned(value, suffix)).toBe(`${expected}${suffix}`);
    }
    expect(formatSigned(null, suffix)).toBe('—');
    expect(formatSigned(undefined, suffix)).toBe('—');
  });

  it('shows nonzero drawdown magnitude below display precision without changing zero or missing', () => {
    expect(formatMagnitude(-2.5, '%')).toBe('2.5%');
    expect(formatMagnitude(-0.004, '%')).toBe('0.004%');
    expect(formatMagnitude(0.004, '%')).toBe('0.004%');
    expect(formatMagnitude(-Number.MIN_VALUE, '%')).toBe('5e-324%');
    expect(formatMagnitude(0, '%')).toBe('0%');
    expect(formatMagnitude(null, '%')).toBe('—');
    expect(formatMagnitude(undefined, '%')).toBe('—');
  });
});
