import { describe, expect, it } from 'vitest';

import {
  BACKTEST_RESULT_SCHEMA_VERSION,
  isBacktestClosedTrade,
  isBacktestRun,
} from '@/types/backtesterContracts';

describe('backtester contract validators', () => {
  it('validates public Backtest Run history payloads', () => {
    expect(isBacktestRun({
      run_id: 'run-queued',
      status: 'queued',
      submitted_at_ms: 1_780_921_805_123,
      request_schema_version: 1,
      request: backtestRequest(),
    })).toBe(true);

    expect(isBacktestRun({
      run_id: 'run-succeeded',
      status: 'succeeded',
      submitted_at_ms: 1_780_921_805_123,
      started_at_ms: 1_780_921_900_000,
      completed_at_ms: 1_780_922_100_000,
      request_schema_version: 1,
      request: backtestRequest(),
      result_schema_version: BACKTEST_RESULT_SCHEMA_VERSION,
      metrics: { total_return_pct: 1.25, trade_count: 1 },
      diagnostics: { execution_duration_ms: 240_000 },
    })).toBe(true);

    expect(isBacktestRun({
      run_id: 'run-failed',
      status: 'failed',
      submitted_at_ms: 1_780_921_805_123,
      started_at_ms: 1_780_921_900_000,
      completed_at_ms: 1_780_922_100_000,
      request_schema_version: 1,
      request: backtestRequest(),
      error_code: 'market_data_unavailable',
      error_message: 'Historical market data is unavailable',
    })).toBe(true);

    expect(isBacktestRun({
      run_id: 'run-old-schema',
      status: 'succeeded',
      submitted_at_ms: 1_780_921_805_123,
      request_schema_version: 1,
      request: backtestRequest(),
      result_schema_version: 1,
      metrics: {},
      diagnostics: {},
    })).toBe(true);

    expect(isBacktestRun({ run_id: 'run-123', status: 'mystery' })).toBe(false);
    expect(isBacktestRun({
      run_id: 'run-123',
      status: 'queued',
      submitted_at_ms: 1_780_921_805_123,
      request_schema_version: 1,
      request: { ...backtestRequest(), symbols: [] },
    })).toBe(false);
    expect(isBacktestRun({
      run_id: 'run-123',
      status: 'succeeded',
      submitted_at_ms: 1_780_921_805_123,
      request_schema_version: 1,
      request: backtestRequest(),
      result_schema_version: '2',
    })).toBe(false);
  });

  it('validates result schema version 2 Backtest Closed Trade payloads', () => {
    expect(isBacktestClosedTrade({
      sequence: 0,
      trade_id: 'trade-1',
      symbol: 'EURUSD',
      quantity: 1_000,
      entry_timestamp_ms: 1_714_525_200_000,
      entry_price: 1.0715,
      exit_timestamp_ms: 1_714_532_400_000,
      exit_price: 1.074,
      realized_pnl: 2.5,
      fees: 0.3,
      exit_reason: 'take_profit',
      stop_loss_price: null,
      take_profit_price: 1.073,
    })).toBe(true);

    expect(isBacktestClosedTrade({
      sequence: 0,
      trade_id: 'trade-1',
      symbol: 'EURUSD',
      quantity: 1_000,
      entry_timestamp_ms: 1_714_525_200_000,
      entry_price: 1.0715,
      exit_timestamp_ms: 1_714_532_400_000,
      exit_price: 1.074,
      realized_pnl: 2.5,
      fees: 0.3,
      exit_reason: 'stop_loss',
      take_profit_price: null,
    })).toBe(false);

    expect(isBacktestClosedTrade({
      sequence: 0,
      trade_id: 'trade-1',
      symbol: 'EURUSD',
      quantity: 1_000,
      entry_timestamp_ms: 1_714_525_200_000,
      entry_price: 1.0715,
      exit_timestamp_ms: 1_714_532_400_000,
      exit_price: 1.074,
      realized_pnl: 2.5,
      fees: 0.3,
      exit_reason: 'manual',
      stop_loss_price: null,
      take_profit_price: null,
    })).toBe(false);
  });
});

function backtestRequest() {
  return {
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
      allow_short: false,
      trade_accounting_policy: 'average_cost',
      gap_policy: 'skip',
      intrabar_exit_policy: 'conservative',
      commission_bps: 1,
      slippage_bps: 0.5,
    },
    persist_result: true,
    run_metadata: null,
  };
}
