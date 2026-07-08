import { describe, expect, it } from 'vitest';

import {
  BACKTEST_RESULT_SCHEMA_VERSION,
  type BacktestClosedTrade,
  isBacktestClosedTrade,
  isBacktestRun,
} from '@/types/backtesterContracts';
import {
  buildBacktestProtectiveLineSegments,
  buildBacktestTradeMarkers,
  BUY_MARKER_COLOR,
  SELL_MARKER_COLOR,
  STOP_LOSS_LINE_COLOR,
  TAKE_PROFIT_LINE_COLOR,
} from '@/utils/chart/backtestOverlay';

const closedTrade = (overrides: Partial<BacktestClosedTrade> = {}): BacktestClosedTrade => ({
  sequence: 0,
  trade_id: 'trade-1',
  symbol: 'EURUSD',
  trade_direction: 'long',
  quantity: 1_000,
  entry_timestamp_ms: 300_000,
  entry_price: 101.25,
  exit_timestamp_ms: 600_000,
  exit_price: 104.5,
  realized_pnl: 3.25,
  fees: 0.25,
  exit_reason: 'signal',
  stop_loss_price: null,
  take_profit_price: null,
  ...overrides,
});

describe('backtest chart overlay utilities', () => {
  it('uses the configured buy and sell colors for trade markers', () => {
    expect(BUY_MARKER_COLOR).toBe('#00E676');
    expect(SELL_MARKER_COLOR).toBe('#FF5252');
  });

  it('accepts persisted short result contracts and renders entry and cover actions', () => {
    const run = {
      run_id: 'run-short-acceptance',
      status: 'succeeded',
      submitted_at_ms: 1_780_921_805_123,
      started_at_ms: 1_780_921_900_000,
      completed_at_ms: 1_780_922_100_000,
      request_schema_version: 2,
      request: {
        symbols: ['AAPL'],
        exchange: null,
        timeframe: '1m',
        start_ms: 1_700_000_000_000,
        end_ms: 1_700_000_420_000,
        engine: 'vectorized',
        data_granularity: 'bar',
        initial_capital: 10_000,
        strategy: {
          strategy_id: 'sma_crossover',
          parameters: {
            fast_window: 2,
            slow_window: 3,
            quantity: 1,
            stop_loss_pct: 5,
            take_profit_pct: 10,
          },
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
          commission_bps: 10,
          slippage_bps: 0,
        },
        persist_result: true,
        run_metadata: null,
      },
      result_schema_version: BACKTEST_RESULT_SCHEMA_VERSION,
      metrics: {
        total_return_pct: -0.0046845,
        max_drawdown_pct: -0.0046845,
        trade_count: 1,
        long_trade_count: 0,
        short_trade_count: 1,
        long_win_rate_pct: 0,
        short_win_rate_pct: 0,
        long_realized_pnl: 0,
        short_realized_pnl: -0.46845,
      },
      diagnostics: { engine: 'vectorized', execution_duration_ms: 12 },
    };
    const shortTrade = closedTrade({
      trade_id: 'AAPL-trade-1',
      symbol: 'AAPL',
      trade_direction: 'short',
      entry_timestamp_ms: 1_700_000_300_000,
      entry_price: 9,
      exit_timestamp_ms: 1_700_000_300_000,
      exit_price: 9.45,
      realized_pnl: -0.46845,
      fees: 0.01845,
      exit_reason: 'stop_loss',
      stop_loss_price: 9.45,
      take_profit_price: 8.1,
    });

    expect(isBacktestRun(run)).toBe(true);
    expect(isBacktestClosedTrade(shortTrade)).toBe(true);
    expect(buildBacktestTradeMarkers([shortTrade], {
      startMs: 1_700_000_000_000,
      endMs: 1_700_000_420_000,
    })).toEqual([
      {
        id: 'AAPL-trade-1:entry',
        time: 1_700_000_300,
        position: 'aboveBar',
        shape: 'arrowDown',
        color: SELL_MARKER_COLOR,
        text: 'Sell @ 9',
      },
      {
        id: 'AAPL-trade-1:exit',
        time: 1_700_000_300,
        position: 'belowBar',
        shape: 'arrowUp',
        color: BUY_MARKER_COLOR,
        text: 'Buy @ 9.45',
      },
    ]);
  });

  it('builds marker actions from closed trade direction', () => {
    const markers = buildBacktestTradeMarkers([
      closedTrade({
        trade_id: 'long-trade',
        trade_direction: 'long',
        entry_timestamp_ms: 300_000,
        entry_price: 101.25,
        exit_timestamp_ms: 600_000,
        exit_price: 104.5,
      }),
      closedTrade({
        trade_id: 'short-trade',
        trade_direction: 'short',
        entry_timestamp_ms: 360_000,
        entry_price: 99.75,
        exit_timestamp_ms: 660_000,
        exit_price: 96.5,
      }),
    ], {
      startMs: 0,
      endMs: 900_000,
    });

    expect(markers).toEqual([
      {
        id: 'long-trade:entry',
        time: 300,
        position: 'belowBar',
        shape: 'arrowUp',
        color: BUY_MARKER_COLOR,
        text: 'Buy @ 101.25',
      },
      {
        id: 'short-trade:entry',
        time: 360,
        position: 'aboveBar',
        shape: 'arrowDown',
        color: SELL_MARKER_COLOR,
        text: 'Sell @ 99.75',
      },
      {
        id: 'long-trade:exit',
        time: 600,
        position: 'aboveBar',
        shape: 'arrowDown',
        color: SELL_MARKER_COLOR,
        text: 'Sell @ 104.5',
      },
      {
        id: 'short-trade:exit',
        time: 660,
        position: 'belowBar',
        shape: 'arrowUp',
        color: BUY_MARKER_COLOR,
        text: 'Buy @ 96.5',
      },
    ]);
  });

  it('formats marker prices with precision derived from symbol min move', () => {
    const markers = buildBacktestTradeMarkers([
      closedTrade({
        entry_price: 101.2,
        exit_price: 104.5,
      }),
    ], {
      startMs: 0,
      endMs: 900_000,
    }, 0.01);

    expect(markers.map((marker) => marker.text)).toEqual([
      'Buy @ 101.20',
      'Sell @ 104.50',
    ]);
  });

  it('builds red stop-loss and blue take-profit segments from persisted closed trade fields', () => {
    const segments = buildBacktestProtectiveLineSegments([
      closedTrade({
        trade_id: 'signal-with-protection',
        exit_reason: 'signal',
        stop_loss_price: 98.5,
        take_profit_price: 108.25,
      }),
    ]);

    expect(segments).toEqual([
      {
        id: 'signal-with-protection:stop-loss',
        startTime: 300,
        endTime: 600,
        price: 98.5,
        color: STOP_LOSS_LINE_COLOR,
      },
      {
        id: 'signal-with-protection:take-profit',
        startTime: 300,
        endTime: 600,
        price: 108.25,
        color: TAKE_PROFIT_LINE_COLOR,
      },
    ]);
  });

  it('does not create segments for null planned protective prices', () => {
    const segments = buildBacktestProtectiveLineSegments([
      closedTrade({
        trade_id: 'stop-only',
        stop_loss_price: 99.75,
        take_profit_price: null,
      }),
      closedTrade({
        trade_id: 'no-protection',
        stop_loss_price: null,
        take_profit_price: null,
      }),
    ]);

    expect(segments).toEqual([
      expect.objectContaining({
        id: 'stop-only:stop-loss',
        price: 99.75,
        color: STOP_LOSS_LINE_COLOR,
      }),
    ]);
  });
});
