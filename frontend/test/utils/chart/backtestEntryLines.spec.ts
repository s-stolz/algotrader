import { describe, expect, it } from 'vitest';
import {
  buildBacktestEntryLines,
  buildOpenPositionEntryLines,
  buildBacktestLimitLines,
} from '@/utils/chart/backtestEntryLines';
import type {
  BacktestClosedTrade,
  BacktestFill,
} from '@/types/backtesterContracts';

const range = {
  startMs: 60000,
  endMs: 359999,
  candleStartsMs: [60000, 120000, 180000, 240000, 300000],
};
const event = (
  outcome: string,
  timestamp_ms: number,
  limit_price?: number,
  order_id = 'buy',
) => ({ outcome, timestamp_ms, limit_price, order_id });

describe('entry and pending limit lines', () => {
  it.each(['long', 'short'] as const)(
    'draws %s entry at actual fill price until close',
    (trade_direction) => {
      const trade = {
        trade_id: 'trade',
        trade_direction,
        entry_timestamp_ms: 90000,
        exit_timestamp_ms: 210000,
        entry_price: 99,
      } as BacktestClosedTrade;
      expect(buildBacktestEntryLines([trade], range)).toEqual([
        expect.objectContaining({
          startTime: 60,
          endTime: 180,
          price: 99,
          dashed: false,
        }),
      ]);
    },
  );
  it.each([
    'filled',
    'cancel',
    'expired',
    'replaced',
    'gap_expired',
    'schedule_cancelled',
    'constraint_cancelled',
    'reduce_only_cancelled',
    'oco_cancelled',
    'stop_cancelled',
    'run_end_expired',
  ])('ends pending price at %s', (outcome) => {
    expect(
      buildBacktestLimitLines(
        [event('submit', 120000, 98), event(outcome, 240000)],
        range,
        360000,
      ),
    ).toEqual([
      expect.objectContaining({
        startTime: 120,
        endTime: 240,
        price: 98,
        dashed: true,
      }),
    ]);
  });
  it('splits price updates, keeps independent orders, and ignores no-op events', () => {
    const lines = buildBacktestLimitLines(
      [
        event('submit', 60000, 98),
        event('submit', 60000, 110, 'sell'),
        event('update', 120000, 97),
        event('inactive_noop', 180000),
        event('filled', 240000),
        event('cancel', 300000, undefined, 'sell'),
      ],
      range,
      360000,
    );
    expect(
      lines.map(({ startTime, endTime, price }) => [startTime, endTime, price]),
    ).toEqual([
      [60, 120, 98],
      [120, 240, 97],
      [60, 300, 110],
    ]);
  });
  it('clips to loaded history and keeps same-candle lifetimes', () => {
    const lines = buildBacktestLimitLines(
      [
        event('submit', 0, 98),
        event('filled', 90000),
        event('submit', 120000, 97, 'other'),
      ],
      range,
      360000,
    );
    expect(lines.map(({ startTime, endTime }) => [startTime, endTime])).toEqual(
      [
        [60, 60],
        [120, 300],
      ],
    );
  });
  it('does not infer prices for legacy or malformed order history', () => {
    expect(buildBacktestLimitLines(undefined, range, 360000)).toEqual([]);
    expect(
      buildBacktestLimitLines(
        [
          null,
          event('submit', 60000),
          event('filled', 120000),
          event('submit', 180000, NaN),
        ],
        range,
        360000,
      ),
    ).toEqual([]);
  });
});

const fill = (
  side: 'buy' | 'sell',
  quantity: number,
  price: number,
  timestamp_ms = 120000,
): BacktestFill => ({
  sequence: 0,
  symbol: 'TEST',
  side,
  quantity,
  price,
  timestamp_ms,
  fees: 0,
  exit_reason: null,
});
describe('entry lines for remaining open positions', () => {
  it.each(['buy', 'sell'] as const)(
    'extends a %s fill through the run boundary',
    (side) => {
      expect(
        buildOpenPositionEntryLines([fill(side, 1, 99)], range, 240000),
      ).toEqual([
        expect.objectContaining({
          startTime: 120,
          endTime: 180,
          price: 99,
          dashed: false,
        }),
      ]);
    },
  );
  it('keeps the average entry after scaling in and partially closing', () => {
    expect(
      buildOpenPositionEntryLines(
        [
          fill('buy', 1, 100),
          fill('buy', 1, 110, 180000),
          fill('sell', 1, 120, 240000),
        ],
        range,
        360000,
      ),
    ).toEqual([
      expect.objectContaining({ startTime: 120, endTime: 300, price: 105 }),
    ]);
  });
  it('starts a flipped position at the reversal fill', () => {
    expect(
      buildOpenPositionEntryLines(
        [fill('buy', 1, 100), fill('sell', 2, 110, 240000)],
        range,
        360000,
      ),
    ).toEqual([
      expect.objectContaining({ startTime: 240, endTime: 300, price: 110 }),
    ]);
  });
  it('does not duplicate closed positions or floating-point residue', () => {
    expect(
      buildOpenPositionEntryLines(
        [fill('buy', 0.1, 100), fill('buy', 0.2, 100), fill('sell', 0.3, 101)],
        range,
        360000,
      ),
    ).toEqual([]);
    expect(buildOpenPositionEntryLines([], range, 360000)).toEqual([]);
  });
  it('clips to loaded candles and excludes history after run end', () => {
    expect(
      buildOpenPositionEntryLines([fill('buy', 1, 100, 0)], range, 180000)[0],
    ).toMatchObject({ startTime: 60, endTime: 120 });
    expect(
      buildOpenPositionEntryLines(
        [fill('buy', 1, 100, 0)],
        { ...range, startMs: 240000 },
        180000,
      ),
    ).toEqual([]);
  });
});
