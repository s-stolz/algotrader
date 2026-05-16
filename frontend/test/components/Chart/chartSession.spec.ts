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

function candleUpdate(timestampMs: number, close = 1.5): CandleUpdateMessage {
  return {
    type: 'candleUpdate',
    symbol: 'EURUSD',
    timeframe: 'M5',
    timestamp_ms: timestampMs,
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
  reportLiveTailBufferOverflow(key: ChartSessionKey, candle: CandleUpdateMessage): void;
  getOldestCandleTimestampMs(): number | null;
  fetchOlderCandles(
    key: ChartSessionKey,
    endMs: number,
  ): Promise<readonly ChartCandle[]> | readonly ChartCandle[];
  prependOlderCandles(key: ChartSessionKey, candles: readonly ChartCandle[]): Promise<void> | void;
  renderOlderCandles(key: ChartSessionKey): Promise<void> | void;
  requestOlderIndicators(key: ChartSessionKey): Promise<void> | void;
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
    reportLiveTailBufferOverflow: vi.fn((key, candle) => {
      events.push(`overflow:${keyLabel(key)}:${candle.timestamp_ms}`);
    }),
    getOldestCandleTimestampMs: vi.fn(() => 300_000),
    fetchOlderCandles: vi.fn((key: ChartSessionKey, endMs: number) => {
      events.push(`fetch-older-candles:${keyLabel(key)}:${endMs}`);
      return Promise.resolve([chartCandle(0)]);
    }),
    prependOlderCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`prepend-older-candles:${keyLabel(key)}`);
    }),
    renderOlderCandles: vi.fn((key: ChartSessionKey) => {
      events.push(`render-older-candles:${keyLabel(key)}`);
    }),
    requestOlderIndicators: vi.fn((key: ChartSessionKey) => {
      events.push(`fetch-older-indicators:${keyLabel(key)}`);
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

  it('buffers current live candles during historical fetch and replays them after render', async () => {
    const { adapter, events, handlers } = createFakeAdapter();
    const fetch = deferred<ChartCandle[]>();
    vi.mocked(adapter.fetchCandles).mockReturnValue(fetch.promise);
    const session = createChartSession(adapter);
    const receiveLiveCandle = vi.fn((message: CandleUpdateMessage) => {
      events.push(`live:${message.timestamp_ms}`);
    });

    const pendingSession = session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, receiveLiveCandle);
    await vi.waitFor(() => {
      expect(adapter.fetchCandles).toHaveBeenCalledOnce();
    });

    for (const handler of handlers) {
      handler(candleUpdate(600_000, 2.5));
    }

    expect(receiveLiveCandle).not.toHaveBeenCalled();

    fetch.resolve([chartCandle(300_000)]);
    await pendingSession;

    expect(receiveLiveCandle).toHaveBeenCalledOnce();
    expect(receiveLiveCandle).toHaveBeenCalledWith(
      expect.objectContaining({
        timestamp_ms: 600_000,
      }),
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
    );
    expect(events.indexOf('render:EURUSD:FX:M5')).toBeLessThan(
      events.indexOf('live:600000'),
    );
  });

  it('coalesces repeated timestamps and replays distinct live tail candles in arrival order', async () => {
    const { adapter, handlers } = createFakeAdapter();
    const fetch = deferred<ChartCandle[]>();
    vi.mocked(adapter.fetchCandles).mockReturnValue(fetch.promise);
    const session = createChartSession(adapter);
    const received: CandleUpdateMessage[] = [];

    const pendingSession = session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, (message) => {
      received.push(message);
    });
    await vi.waitFor(() => {
      expect(adapter.fetchCandles).toHaveBeenCalledOnce();
    });

    for (const handler of handlers) {
      handler(candleUpdate(600_000, 2.5));
      handler(candleUpdate(600_000, 2.6));
      handler(candleUpdate(900_000, 3.5));
      handler(candleUpdate(800_000, 9.9));
    }

    fetch.resolve([chartCandle(300_000)]);
    await pendingSession;

    expect(received.map((message) => [message.timestamp_ms, message.close])).toEqual([
      [600_000, 2.6],
      [900_000, 3.5],
    ]);
  });

  it('reports live tail overflow and refetches the current session without user notification', async () => {
    const { adapter, handlers } = createFakeAdapter();
    const firstFetch = deferred<ChartCandle[]>();
    const refetch = deferred<ChartCandle[]>();
    const notifyUser = vi.fn();
    let fetchCount = 0;
    vi.mocked(adapter.fetchCandles).mockImplementation(() => {
      fetchCount += 1;
      return fetchCount === 1 ? firstFetch.promise : refetch.promise;
    });
    const adapterWithNotificationSentinel: ChartSessionSubscriptionsAdapter & {
      notifyUser: () => void;
    } = {
      ...adapter,
      notifyUser,
    };
    const session = createChartSession(adapterWithNotificationSentinel);

    const pendingSession = session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());
    await vi.waitFor(() => {
      expect(adapter.fetchCandles).toHaveBeenCalledOnce();
    });

    for (const handler of handlers) {
      handler(candleUpdate(600_000));
      handler(candleUpdate(900_000));
      handler(candleUpdate(1_200_000));
      handler(candleUpdate(1_500_000));
    }

    await vi.waitFor(() => {
      expect(adapter.fetchCandles).toHaveBeenCalledTimes(2);
    });
    expect(adapter.reportLiveTailBufferOverflow).toHaveBeenCalledWith(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      expect.objectContaining({
        timestamp_ms: 1_500_000,
      }),
    );
    expect(notifyUser).not.toHaveBeenCalled();

    firstFetch.resolve([chartCandle(300_000)]);
    await pendingSession;
    const refetchedCandles = [chartCandle(1_500_000)];
    refetch.resolve(refetchedCandles);
    await vi.waitFor(() => {
      expect(adapter.renderCandles).toHaveBeenCalledWith(
        {
          symbol: 'EURUSD',
          exchange: 'FX',
          timeframe: 'M5',
        },
        refetchedCandles,
      );
    });
  });

  it('ignores an overflow refetch result after the session key changes', async () => {
    const { adapter, handlers } = createFakeAdapter();
    const firstFetch = deferred<ChartCandle[]>();
    const staleRefetch = deferred<ChartCandle[]>();
    const currentCandles = [chartCandle(2_100_000)];
    let eurUsdFetchCount = 0;
    vi.mocked(adapter.fetchCandles).mockImplementation((key) => {
      if (key.symbol === 'EURUSD') {
        eurUsdFetchCount += 1;
        return eurUsdFetchCount === 1 ? firstFetch.promise : staleRefetch.promise;
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
      expect(adapter.fetchCandles).toHaveBeenCalledOnce();
    });

    for (const handler of handlers) {
      handler(candleUpdate(600_000));
      handler(candleUpdate(900_000));
      handler(candleUpdate(1_200_000));
      handler(candleUpdate(1_500_000));
    }
    await vi.waitFor(() => {
      expect(adapter.fetchCandles).toHaveBeenCalledTimes(2);
    });

    await session.setSession({
      symbol: 'GBPUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    firstFetch.resolve([chartCandle(300_000)]);
    await firstSession;
    staleRefetch.resolve([chartCandle(1_500_000)]);
    await new Promise((resolve) => {
      setTimeout(resolve, 0);
    });

    expect(adapter.renderCandles).not.toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: 'EURUSD',
        timeframe: 'M5',
      }),
      expect.anything(),
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
});

describe('chart session older history paging', () => {
  it('requests older candle and indicator history with the current session key', async () => {
    const { adapter } = createFakeAdapter();
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    session.requestOlderHistory({
      barsBefore: 99,
      nowMs: 1_000,
    });
    await vi.waitFor(() => {
      expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
      expect(adapter.renderOlderCandles).toHaveBeenCalledOnce();
    });

    expect(adapter.fetchOlderCandles).toHaveBeenCalledWith(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      300_000,
    );
    expect(adapter.prependOlderCandles).toHaveBeenCalledWith(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      [chartCandle(0)],
    );
    expect(adapter.renderOlderCandles).toHaveBeenCalledWith({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    });
    expect(adapter.requestOlderIndicators).toHaveBeenCalledWith({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    });
  });

  it('uses the latest active key for older history after a session change', async () => {
    const { adapter } = createFakeAdapter();
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());
    await session.setSession({
      symbol: 'GBPUSD',
      exchange: 'CFD',
      timeframe: 'H1',
    }, vi.fn());
    vi.mocked(adapter.fetchOlderCandles).mockClear();
    vi.mocked(adapter.requestOlderIndicators).mockClear();

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_000,
    });
    await vi.waitFor(() => {
      expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
    });

    expect(adapter.fetchOlderCandles).toHaveBeenCalledWith(
      {
        symbol: 'GBPUSD',
        exchange: 'CFD',
        timeframe: 'H1',
      },
      300_000,
    );
    expect(adapter.requestOlderIndicators).toHaveBeenCalledWith({
      symbol: 'GBPUSD',
      exchange: 'CFD',
      timeframe: 'H1',
    });
    expect(adapter.fetchOlderCandles).not.toHaveBeenCalledWith(
      expect.objectContaining({
        symbol: 'EURUSD',
        timeframe: 'M5',
      }),
      expect.anything(),
    );
  });

  it('suppresses older history paging while scroll-to-realtime is pending', async () => {
    const { adapter } = createFakeAdapter();
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_000,
      scrollToRealtime: true,
    });

    expect(adapter.fetchOlderCandles).not.toHaveBeenCalled();
    expect(adapter.requestOlderIndicators).not.toHaveBeenCalled();
  });

  it('does not start duplicate older history loads while a previous page is in flight', async () => {
    const { adapter } = createFakeAdapter();
    const olderCandles = deferred<ChartCandle[]>();
    const olderIndicators = deferred<void>();
    vi.mocked(adapter.fetchOlderCandles).mockReturnValue(olderCandles.promise);
    vi.mocked(adapter.requestOlderIndicators).mockReturnValue(olderIndicators.promise);
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_000,
    });
    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_100,
    });

    expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
    expect(adapter.requestOlderIndicators).toHaveBeenCalledOnce();

    olderCandles.resolve([chartCandle(0)]);
    olderIndicators.resolve();
    await vi.waitFor(() => {
      expect(adapter.prependOlderCandles).toHaveBeenCalledOnce();
    });
  });

  it('honors the older history cooldown after a page load settles', async () => {
    const { adapter } = createFakeAdapter();
    const session = createChartSession(adapter);

    await session.setSession({
      symbol: 'EURUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }, vi.fn());

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_000,
    });
    await vi.waitFor(() => {
      expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
      expect(adapter.requestOlderIndicators).toHaveBeenCalledOnce();
      expect(adapter.renderOlderCandles).toHaveBeenCalledOnce();
    });

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_200,
    });

    expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
    expect(adapter.requestOlderIndicators).toHaveBeenCalledOnce();

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_400,
    });
    await vi.waitFor(() => {
      expect(adapter.fetchOlderCandles).toHaveBeenCalledTimes(2);
      expect(adapter.requestOlderIndicators).toHaveBeenCalledTimes(2);
    });
  });
});
