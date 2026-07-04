import { describe, expect, it } from 'vitest';

import type { BacktestClosedTrade } from '@/types/backtesterContracts';
import {
  buildBacktestProtectiveLineSegments,
  STOP_LOSS_LINE_COLOR,
  TAKE_PROFIT_LINE_COLOR,
} from '@/utils/chart/backtestOverlay';

const closedTrade = (overrides: Partial<BacktestClosedTrade> = {}): BacktestClosedTrade => ({
  sequence: 0,
  trade_id: 'trade-1',
  symbol: 'EURUSD',
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
