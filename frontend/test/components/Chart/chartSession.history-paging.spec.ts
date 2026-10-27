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
      expect(adapter.requestOlderIndicators).toHaveBeenCalledOnce();

      olderCandles.resolve([chartCandle(0)]);
      olderIndicators.resolve();
      await vi.waitFor(() => {
        expect(adapter.prependOlderCandles).toHaveBeenCalledOnce();
      });
    },
  );

  it('honors the older history cooldown after a page load settles', async () => {
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
