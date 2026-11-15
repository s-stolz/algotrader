import { describe, expect, it, vi } from 'vitest';
import {
  createChartSession,
  type ChartSessionSubscriptionsAdapter,
} from '@/components/Chart/chartSession';
import type { CandleUpdateMessage, ChartCandle } from '@/types/contracts';
import {
  chartCandle,
  candleUpdate,
  deferred,
  createFakeAdapter,
} from './chartSession.fixtures';

describe('chart session candle fetch sequencing', () => {
  it(
    'requests the live candle subscription before starting the' +
      ' historical candle fetch',
    async () => {
      const { adapter, events } = createFakeAdapter();
      const session = createChartSession(adapter);

      await session.setSession(
        {
          symbol: 'EURUSD',
          exchange: 'FX',
          timeframe: 'M5',
        },
        vi.fn(),
      );

      expect(events.indexOf('subscribe:EURUSD:FX:M5')).toBeLessThan(
        events.indexOf('fetch:EURUSD:FX:M5'),
      );
    },
  );

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
    const firstSession = session.setSession(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );
    await vi.waitFor(() => {
      expect(adapter.fetchCandles).toHaveBeenCalledWith({
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      });
    });

    await session.setSession(
      {
        symbol: 'GBPUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );

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

    await session.setSession(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );

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

    await session.setSession(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );
    vi.mocked(adapter.unsubscribeIndicators).mockClear();

    await session.setSession(
      {
        symbol: 'GBPUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );

    expect(adapter.unsubscribeIndicators).toHaveBeenCalledOnce();
  });

  it(
    'buffers current live candles during historical fetch and' +
      ' replays them after render',
    async () => {
      const { adapter, events, handlers } = createFakeAdapter();
      const fetch = deferred<ChartCandle[]>();
      vi.mocked(adapter.fetchCandles).mockReturnValue(fetch.promise);
      const session = createChartSession(adapter);
      const receiveLiveCandle = vi.fn((message: CandleUpdateMessage) => {
        events.push(`live:${message.timestamp_ms}`);
      });

      const pendingSession = session.setSession(
        {
          symbol: 'EURUSD',
          exchange: 'FX',
          timeframe: 'M5',
        },
        receiveLiveCandle,
      );
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
    },
  );

  it(
    'coalesces repeated timestamps and replays distinct live' +
      ' tail candles in arrival order',
    async () => {
      const { adapter, handlers } = createFakeAdapter();
      const fetch = deferred<ChartCandle[]>();
      vi.mocked(adapter.fetchCandles).mockReturnValue(fetch.promise);
      const session = createChartSession(adapter);
      const received: CandleUpdateMessage[] = [];

      const pendingSession = session.setSession(
        {
          symbol: 'EURUSD',
          exchange: 'FX',
          timeframe: 'M5',
        },
        (message) => {
          received.push(message);
        },
      );
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

      expect(
        received.map((message) => [message.timestamp_ms, message.close]),
      ).toEqual([
        [600_000, 2.6],
        [900_000, 3.5],
      ]);
    },
  );

  it(
    'reports live tail overflow and refetches the current' +
      ' session without user notification',
    async () => {
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

      const pendingSession = session.setSession(
        {
          symbol: 'EURUSD',
          exchange: 'FX',
          timeframe: 'M5',
        },
        vi.fn(),
      );
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
    },
  );

  it('ignores an overflow refetch result after the session key changes', async () => {
    const { adapter, handlers } = createFakeAdapter();
    const firstFetch = deferred<ChartCandle[]>();
    const staleRefetch = deferred<ChartCandle[]>();
    const currentCandles = [chartCandle(2_100_000)];
    let eurUsdFetchCount = 0;
    vi.mocked(adapter.fetchCandles).mockImplementation((key) => {
      if (key.symbol === 'EURUSD') {
        eurUsdFetchCount += 1;
        return eurUsdFetchCount === 1
          ? firstFetch.promise
          : staleRefetch.promise;
      }

      return Promise.resolve(currentCandles);
    });
    const session = createChartSession(adapter);

    const firstSession = session.setSession(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );
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

    await session.setSession(
      {
        symbol: 'GBPUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );

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
