import { describe, expect, it, vi } from 'vitest';
import { createChartSession } from '@/components/Chart/chartSession';
import type { ChartCandle } from '@/types/contracts';
import {
  chartCandle,
  deferred,
  createFakeAdapter,
} from './chartSession.fixtures';

describe('chart session older history paging', () => {
  it('requests older candle and indicator history with the current session key', async () => {
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

    await session.setSession(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );
    await session.setSession(
      {
        symbol: 'GBPUSD',
        exchange: 'CFD',
        timeframe: 'H1',
      },
      vi.fn(),
    );
    vi.mocked(adapter.fetchOlderCandles).mockClear();
    vi.mocked(adapter.requestOlderIndicators).mockClear();

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_000,
    });
    await vi.waitFor(() => {
      expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
      expect(adapter.requestOlderIndicators).toHaveBeenCalledOnce();
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

    await session.setSession(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );

    session.requestOlderHistory({
      barsBefore: 10,
      nowMs: 1_000,
      scrollToRealtime: true,
    });

    expect(adapter.fetchOlderCandles).not.toHaveBeenCalled();
    expect(adapter.requestOlderIndicators).not.toHaveBeenCalled();
  });

  it(
    'does not start duplicate older history loads while a' +
      ' previous page is in flight',
    async () => {
      const { adapter } = createFakeAdapter();
      const olderCandles = deferred<ChartCandle[]>();
      const olderIndicators = deferred<void>();
      vi.mocked(adapter.fetchOlderCandles).mockReturnValue(
        olderCandles.promise,
      );
      vi.mocked(adapter.requestOlderIndicators).mockReturnValue(
        olderIndicators.promise,
      );
      const session = createChartSession(adapter);

      await session.setSession(
        {
          symbol: 'EURUSD',
          exchange: 'FX',
          timeframe: 'M5',
        },
        vi.fn(),
      );

      session.requestOlderHistory({
        barsBefore: 10,
        nowMs: 1_000,
      });
      session.requestOlderHistory({
        barsBefore: 10,
        nowMs: 1_100,
      });

      expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
      expect(adapter.requestOlderIndicators).not.toHaveBeenCalled();

      olderCandles.resolve([chartCandle(0)]);
      olderIndicators.resolve();
      await vi.waitFor(() => {
        expect(adapter.prependOlderCandles).toHaveBeenCalledOnce();
      });
    },
  );

  it('does not repeat requests after reaching the oldest candle', async () => {
    const { adapter } = createFakeAdapter();
    vi.mocked(adapter.fetchOlderCandles).mockResolvedValue([]);
    const session = createChartSession(adapter);

    await session.setSession(
      {
        symbol: 'EURUSD',
        exchange: 'FX',
        timeframe: 'M5',
      },
      vi.fn(),
    );

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
      expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
      expect(adapter.requestOlderIndicators).toHaveBeenCalledOnce();
    });
  });
});

it('fills a wide live viewport when render reports demand during an in-flight page', async () => {
  const { adapter } = createFakeAdapter();
  const session = createChartSession(adapter);
  let oldest = 1_000_000_000;
  let remaining = -900;
  vi.mocked(adapter.getOldestCandleTimestampMs).mockImplementation(
    () => oldest,
  );
  vi.mocked(adapter.fetchOlderCandles).mockImplementation(async () =>
    Array.from({ length: 500 }, (_, i) =>
      chartCandle(oldest - (500 - i) * 300_000),
    ),
  );
  vi.mocked(adapter.prependOlderCandles).mockImplementation((_key, candles) => {
    oldest = candles[0].timestamp_ms;
  });
  vi.mocked(adapter.renderOlderCandles).mockImplementation(() => {
    remaining += 500;
    session.requestOlderHistory({ barsBefore: remaining, nowMs: 2000 });
  });
  await session.setSession({ symbol: 'EURUSD', timeframe: 'M5' }, vi.fn());
  session.requestOlderHistory({ barsBefore: remaining, nowMs: 1000 });
  await vi.waitFor(() =>
    expect(adapter.fetchOlderCandles).toHaveBeenCalledTimes(2),
  );
  expect(remaining).toBe(100);
  await session.stop();
});

it('rechecks the current viewport after a page instead of continuing stale demand', async () => {
  const { adapter } = createFakeAdapter();
  const session = createChartSession(adapter);
  const page = deferred<ReturnType<typeof chartCandle>[]>();
  let oldest = 300_000;
  adapter.getHistoryRange = () => ({ barsBefore: 1000, nowMs: 2000 });
  vi.mocked(adapter.getOldestCandleTimestampMs).mockImplementation(
    () => oldest,
  );
  vi.mocked(adapter.fetchOlderCandles).mockReturnValue(page.promise);
  vi.mocked(adapter.prependOlderCandles).mockImplementation((_key, data) => {
    oldest = data[0].timestamp_ms;
  });
  await session.setSession({ symbol: 'EURUSD', timeframe: 'M5' }, vi.fn());
  session.requestOlderHistory({ barsBefore: -900, nowMs: 1000 });
  page.resolve(
    Array.from({ length: 500 }, (_, i) => chartCandle(-(500 - i) * 300_000)),
  );
  await vi.waitFor(() =>
    expect(adapter.requestOlderIndicators).toHaveBeenCalledOnce(),
  );
  expect(adapter.fetchOlderCandles).toHaveBeenCalledOnce();
  await session.stop();
});

it('discards a pending older page when the chart session stops', async () => {
  const { adapter } = createFakeAdapter();
  const session = createChartSession(adapter);
  const page = deferred<ReturnType<typeof chartCandle>[]>();
  vi.mocked(adapter.fetchOlderCandles).mockReturnValue(page.promise);
  await session.setSession({ symbol: 'EURUSD', timeframe: 'M5' }, vi.fn());
  session.requestOlderHistory({ barsBefore: -900, nowMs: 1000 });
  await session.stop();
  page.resolve([chartCandle(0)]);
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(adapter.prependOlderCandles).not.toHaveBeenCalled();
  expect(adapter.requestOlderIndicators).not.toHaveBeenCalled();
});
