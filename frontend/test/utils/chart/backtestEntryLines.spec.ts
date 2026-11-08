import { describe, expect, it } from 'vitest';
import {
  buildBacktestEntryLines,
  buildBacktestLimitLines,
} from '@/utils/chart/backtestEntryLines';
import type { BacktestClosedTrade } from '@/types/backtesterContracts';

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
