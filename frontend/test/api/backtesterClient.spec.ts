import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  deleteBacktestRun,
  fetchBacktestClosedTrades,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

describe('backtester API client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('lists Backtest Runs through the public backtester proxy', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([
      backtestRun({ run_id: 'run-newer' }),
      backtestRun({ run_id: 'run-older', status: 'failed' }),
    ]));

    await expect(listBacktestRuns({
      status: 'succeeded',
      symbol: 'EURUSD',
      timeframe: 'M15',
      strategy: 'sma_crossover',
      engine: 'event_driven',
      submittedFromMs: 1_780_921_800_000,
      submittedToMs: 1_780_922_100_000,
    })).resolves.toEqual([
      backtestRun({ run_id: 'run-newer' }),
      backtestRun({ run_id: 'run-older', status: 'failed' }),
    ]);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/backtester/backtests?status=succeeded&symbol=EURUSD&timeframe=M15&strategy=sma_crossover&engine=event_driven&submitted_from_ms=1780921800000&submitted_to_ms=1780922100000',
    );
  });

  it('fetches one Backtest Run by run id through the public backtester proxy', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(backtestRun({ run_id: 'run-123' })),
    );

    await expect(getBacktestRun('run-123')).resolves.toEqual(backtestRun({ run_id: 'run-123' }));
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/run-123');
  });

  it('fetches result schema version 3 closed trades for a Backtest Run', async () => {
    const trades = [
      {
        sequence: 0,
        trade_id: 'trade-1',
        symbol: 'EURUSD',
        trade_direction: 'short',
        quantity: 1_000,
        entry_timestamp_ms: 1_714_525_200_000,
        entry_price: 1.0715,
        exit_timestamp_ms: 1_714_532_400_000,
        exit_price: 1.074,
        realized_pnl: 2.5,
        fees: 0.3,
        exit_reason: 'signal',
        stop_loss_price: 1.069,
        take_profit_price: 1.075,
      },
    ];
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(trades));

    await expect(fetchBacktestClosedTrades('run-123')).resolves.toEqual(trades);
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/run-123/trades');
  });

  it('deletes one Backtest Run through the public backtester proxy', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 204 }),
    );

    await expect(deleteBacktestRun('run-123')).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith('/api/backtester/backtests/run-123', {
      method: 'DELETE',
    });
  });

  it('surfaces delete failures from the public backtester proxy', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 409, statusText: 'Conflict' }),
    );

    await expect(deleteBacktestRun('run-running')).rejects.toThrow(
      'Failed to delete backtest run: Conflict',
    );
  });

  it('rejects malformed Backtest Run and closed-trade responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([{ run_id: 'run-123' }]));
    await expect(listBacktestRuns()).rejects.toThrow('Invalid backtest runs response');

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({ run_id: 'run-123' }));
    await expect(getBacktestRun('run-123')).rejects.toThrow('Invalid backtest run response');

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([{
      sequence: 0,
      trade_id: 'trade-1',
      symbol: 'EURUSD',
    }]));
    await expect(fetchBacktestClosedTrades('run-123')).rejects.toThrow(
      'Invalid backtest closed trades response',
    );
  });
});

function backtestRun(overrides: Record<string, unknown> = {}) {
  return {
    run_id: 'run-123',
    status: 'succeeded',
    submitted_at_ms: 1_780_921_805_123,
    started_at_ms: 1_780_921_900_000,
    completed_at_ms: 1_780_922_100_000,
    request_schema_version: 2,
    request: {
      symbols: ['EURUSD'],
      exchange: 'FX',
      timeframe: 'M15',
      start_ms: 1_714_521_600_000,
      end_ms: 1_714_608_000_000,
      engine: 'event_driven',
      data_granularity: 'bar',
      initial_capital: 10_000,
      strategy: {
        strategy_id: 'sma_crossover',
        parameters: { fast_window: 10, slow_window: 20 },
      },
      execution: {
        signal_timing: 'close',
        fill_timing: 'next_open',
        price_source: 'open',
        allow_partial_fills: false,
        allowed_directions: 'long_and_short',
        trade_accounting_policy: 'average_cost',
        gap_policy: 'skip',
        intrabar_exit_policy: 'conservative',
        commission_bps: 1,
        slippage_bps: 0.5,
      },
      persist_result: true,
      run_metadata: null,
    },
    result_schema_version: 3,
    metrics: { total_return_pct: 1.25, trade_count: 1, long_trade_count: 1, short_trade_count: 0 },
    diagnostics: { execution_duration_ms: 240_000 },
    ...overrides,
  };
}
