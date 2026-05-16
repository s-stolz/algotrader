import { describe, expect, it, vi } from 'vitest';

import {
  createChartSession,
  type ChartSessionKey,
  type ChartSessionSubscriptionsAdapter,
} from '@/components/Chart/chartSession';
import type { CandleUpdateMessage } from '@/types/contracts';

function createFakeAdapter() {
  const handlers = new Set<(message: CandleUpdateMessage) => void>();
  const subscribes: ChartSessionKey[] = [];
  const unsubscribes: ChartSessionKey[] = [];

  const adapter: ChartSessionSubscriptionsAdapter = {
    subscribeCandles: vi.fn((key) => {
      subscribes.push({ ...key });
    }),
    unsubscribeCandles: vi.fn((key) => {
      unsubscribes.push({ ...key });
    }),
    onCandleUpdate: vi.fn((handler) => {
      handlers.add(handler);
    }),
    offCandleUpdate: vi.fn((handler) => {
      handlers.delete(handler);
    }),
  };

  return {
    adapter,
    handlers,
    subscribes,
    unsubscribes,
  };
}

describe('chart session subscription ownership', () => {
  it('unsubscribes the previous market key and subscribes the new market key', async () => {
    const { adapter, subscribes, unsubscribes } = createFakeAdapter();
    const session = createChartSession(adapter);
    const receiveLiveCandle = vi.fn();

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, receiveLiveCandle);
    await session.setSession({
      symbol: 'GBPUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, receiveLiveCandle);

    expect(unsubscribes).toEqual([
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
    ]);
    expect(subscribes).toEqual([
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      {
        symbol: 'GBPUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
    ]);
  });

  it('unsubscribes the previous timeframe key and subscribes the new timeframe key', async () => {
    const { adapter, subscribes, unsubscribes } = createFakeAdapter();
    const session = createChartSession(adapter);
    const receiveLiveCandle = vi.fn();

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M1',
    }, receiveLiveCandle);
    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'H1',
    }, receiveLiveCandle);

    expect(unsubscribes).toEqual([
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M1',
      },
    ]);
    expect(subscribes).toEqual([
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M1',
      },
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'H1',
      },
    ]);
  });

  it('applies live candles only when they match the active same-timeframe session', async () => {
    const { adapter, handlers } = createFakeAdapter();
    const session = createChartSession(adapter);
    const receiveLiveCandle = vi.fn();

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, receiveLiveCandle);

    for (const handler of handlers) {
      handler({
        type: 'candleUpdate',
        symbol: 'EURUSD',
        timeframe: 'M1',
        timestamp_ms: 60_000,
        open: 1,
        high: 2,
        low: 0.5,
        close: 1.5,
        volume: 10,
      });
      handler({
        type: 'candleUpdate',
        symbol: 'EURUSD',
        timeframe: 'M5',
        timestamp_ms: 300_000,
        open: 1,
        high: 2,
        low: 0.5,
        close: 1.5,
        volume: 10,
      });
    }

    expect(receiveLiveCandle).toHaveBeenCalledOnce();
    expect(receiveLiveCandle).toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: 'EURUSD',
        timeframe: 'M5',
        timestamp_ms: 300_000,
      }),
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
    );
  });
});
