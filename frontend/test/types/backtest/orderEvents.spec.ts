import { describe, expect, it } from 'vitest';
import { readOrderEvents } from '@/types/backtest/orderEvents';

const valid = {
  timestamp_ms: 60000,
  order_id: 'entry',
  outcome: 'sizing',
  mode: 'risk',
  requested_budget: 100,
  quantity: 20,
  stop_price: 95,
  reason: null,
};

describe('saved order event validation', () => {
  it('retains typed sizing fields and valid lifecycle events in saved order', () => {
    expect(
      readOrderEvents({
        order_events: [
          valid,
          {
            timestamp_ms: 120000,
            order_id: '',
            outcome: 'account_depleted',
          },
        ],
      }),
    ).toEqual({
      events: [
        { ...valid, index: 0 },
        {
          index: 1,
          timestamp_ms: 120000,
          order_id: '',
          outcome: 'account_depleted',
        },
      ],
      invalidEventCount: 0,
    });
  });

  it.each([undefined, NaN, Infinity, 8.64e15 + 1, '60000', 1.5, {}])(
    'rejects timestamps that cannot be rendered as epoch milliseconds: %s',
    (timestamp_ms) => {
      expect(
        readOrderEvents({ order_events: [{ ...valid, timestamp_ms }] }),
      ).toEqual({ events: [], invalidEventCount: 1 });
    },
  );

  it('skips corrupt records without hiding valid events or accepting raw cells', () => {
    const parsed = readOrderEvents({
      order_events: [
        { ...valid, equity: {} },
        { ...valid, quantity: Infinity },
        { ...valid, reason: [] },
        null,
        { ...valid, outcome: '' },
        valid,
      ],
    });
    expect(parsed.invalidEventCount).toBe(5);
    expect(parsed.events).toEqual([{ ...valid, index: 5 }]);
    expect(() =>
      new Date(parsed.events[0].timestamp_ms).toISOString(),
    ).not.toThrow();
  });

  it('accepts legacy missing diagnostics and reports malformed event collections', () => {
    for (const diagnostics of [undefined, null, {}, { order_events: null }])
      expect(readOrderEvents(diagnostics)).toEqual({
        events: [],
        invalidEventCount: 0,
      });
    expect(readOrderEvents({ order_events: {} })).toEqual({
      events: [],
      invalidEventCount: 1,
    });
  });
});
