import { describe, expect, it } from 'vitest';
import {
  buildBacktestTradeMarkers,
  orderCandleRange,
} from '@/utils/chart/backtestOverlay';
import type { BacktestClosedTrade } from '@/types/backtesterContracts';

describe('intrabar trade markers', () => {
  it('anchors fills to the containing candle including the last loaded candle', () => {
    const range = orderCandleRange([0, 600_000], 'M10')!;
    const trade: BacktestClosedTrade = {
      sequence: 0,
      trade_id: 'partial',
      symbol: 'TEST',
      trade_direction: 'long',
      quantity: 1,
      entry_timestamp_ms: 660_000,
      entry_price: 99,
      exit_timestamp_ms: 780_000,
      exit_price: 101,
      realized_pnl: 2,
      fees: 0,
      exit_reason: 'take_profit',
      stop_loss_price: 98,
      take_profit_price: 101,
    };
    expect(
      buildBacktestTradeMarkers([trade], range).map((marker) => marker.time),
    ).toEqual([600, 600]);
    expect(trade.entry_timestamp_ms).toBe(660_000);
  });
  it('uses calendar month endings', () => {
    const start = Date.UTC(2026, 1, 1);
    expect(orderCandleRange([start], 'MN1')?.endMs).toBe(
      Date.UTC(2026, 2, 1) - 1,
    );
  });
});
