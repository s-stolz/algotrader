import { describe, expect, it, vi } from 'vitest';

import {
  createChartSession,
  type ChartSessionKey,
  type ChartSessionSubscriptionsAdapter,
} from '@/components/Chart/chartSession';
import type { CandleUpdateMessage, ChartCandle } from '@/types/contracts';

function keyLabel(key: ChartSessionKey): string {
  return `${key.symbol}:${key.exchange ?? ''}:${key.timeframe}`;
}

function chartCandle(timestampMs: number, close = 1.5): ChartCandle {
  return {
    timestamp_ms: timestampMs,
    time: Math.floor(timestampMs / 1000),
    open: 1,
    high: 2,
    low: 0.5,
    close,
    volume: 10,
  };
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });

  return {
    promise,
    resolve,
  };
}

type FakeChartSessionAdapter = ChartSessionSubscriptionsAdapter & {
  fetchCandles(key: ChartSessionKey): Promise<readonly ChartCandle[]> | readonly ChartCandle[];
  renderCandles(key: ChartSessionKey, candles: readonly ChartCandle[]): void;
  requestIndicators(key: ChartSessionKey): Promise<void> | void;
  unsubscribeIndicators(): Promise<void> | void;
  resetIndicatorHistory(): void;
};

function createFakeAdapter() {
  const handlers = new Set<(message: CandleUpdateMessage) => void>();
  const subscribes: ChartSessionKey[] = [];
  const unsubscribes: ChartSessionKey[] = [];
  const events: string[] = [];
  const fetchedCandles = [chartCandle(300_000)];

  const adapter: FakeChartSessionAdapter = {
    subscribeCandles: vi.fn((key) => {
      subscribes.push({ ...key });
      events.push(`subscribe:${keyLabel(key)}`);
    }),
    unsubscribeCandles: vi.fn((key) => {
      unsubscribes.push({ ...key });
      events.push(`unsubscribe:${keyLabel(key)}`);
    }),
    onCandleUpdate: vi.fn((handler) => {
      handlers.add(handler);
    }),
    offCandleUpdate: vi.fn((handler) => {
      handlers.delete(handler);
    }),
    fetchCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`fetch:${keyLabel(key)}`);
      return Promise.resolve(fetchedCandles);
    }),
    renderCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`render:${keyLabel(key)}`);
    }),
    requestIndicators: vi.fn((key: ChartSessionKey) => {
      events.push(`indicators:${keyLabel(key)}`);
    }),
    unsubscribeIndicators: vi.fn(() => {
      events.push('unsubscribe-indicators');
    }),
    resetIndicatorHistory: vi.fn(() => {
      events.push('reset-indicator-history');
    }),
  };

  return {
    adapter,
    events,
    fetchedCandles,
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

  it('does not let a stale pending subscribe unsubscribe a key that became active again', async () => {
    const { adapter, subscribes, unsubscribes, handlers } = createFakeAdapter();
    let resolveFirstSubscribe: (() => void) | undefined;
    let subscribeCount = 0;
    vi.mocked(adapter.subscribeCandles).mockImplementation((key) => {
      subscribes.push({ ...key });
      subscribeCount += 1;

      if (subscribeCount === 1) {
        return new Promise<void>((resolve) => {
          resolveFirstSubscribe = resolve;
        });
      }

      return undefined;
    });
    const session = createChartSession(adapter);
    const receiveLiveCandle = vi.fn();
    const marketA = {
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    };
    const marketB = {
      symbol: 'GBPUSD',
      exchange: 'FX',
      timeframe: 'M5',
    };

    const firstSession = session.setSession(marketA, receiveLiveCandle);
    await session.setSession(marketB, receiveLiveCandle);
    await session.setSession(marketA, receiveLiveCandle);

    resolveFirstSubscribe?.();
    await firstSession;

    expect(unsubscribes).toEqual([
      marketA,
      marketB,
    ]);

    for (const handler of handlers) {
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

    expect(receiveLiveCandle).toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: 'EURUSD',
        timeframe: 'M5',
      }),
      marketA,
    );
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

describe('chart session candle fetch sequencing', () => {
  it('requests the live candle subscription before starting the historical candle fetch', async () => {
    const { adapter, events } = createFakeAdapter();
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    expect(events.indexOf('subscribe:EURUSD:FX:M5')).toBeLessThan(
      events.indexOf('fetch:EURUSD:FX:M5'),
    );
  });

  it('ignores a stale historical candle fetch result after the session key changes', async () => {
    const { adapter } = createFakeAdapter();
    const firstFetch = deferred<ChartCandle[]>();
    const currentCandles = [chartCandle(600_000, 2.5)];

    vi.mocked(adapter.fetchCandles).mockImplementation((key) => {
      if (key.symbol === 'EURUSD') {
        return firstFetch.promise;
      }

      return Promise.resolve(currentCandles);
    });

    const session = createChartSession(adapter);
    const firstSession = session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());
    await vi.waitFor(() => {
      expect(adapter.fetchCandles).toHaveBeenCalledWith({
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      });
    });

    await session.setSession({
      symbol: 'GBPUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    firstFetch.resolve([chartCandle(300_000)]);
    await firstSession;

    expect(adapter.renderCandles).not.toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: 'EURUSD',
        timeframe: 'M5',
      }),
      expect.anything(),
    );
    expect(adapter.requestIndicators).not.toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: 'EURUSD',
        timeframe: 'M5',
      }),
    );
    expect(adapter.renderCandles).toHaveBeenCalledWith(
      {
        symbol: 'GBPUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      currentCandles,
    );
  });

  it('renders the current fetch result before requesting indicators for the same key', async () => {
    const { adapter, events, fetchedCandles } = createFakeAdapter();
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    expect(adapter.renderCandles).toHaveBeenCalledWith(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      fetchedCandles,
    );
    expect(adapter.requestIndicators).toHaveBeenCalledWith({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    });
    expect(events.indexOf('render:EURUSD:FX:M5')).toBeLessThan(
      events.indexOf('indicators:EURUSD:FX:M5'),
    );
  });

  it('unsubscribes old live indicator streams when the session changes', async () => {
    const { adapter } = createFakeAdapter();
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());
    vi.mocked(adapter.unsubscribeIndicators).mockClear();

    await session.setSession({
      symbol: 'GBPUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    expect(adapter.unsubscribeIndicators).toHaveBeenCalledOnce();
  });
});
