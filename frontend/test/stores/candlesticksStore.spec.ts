import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchCandles } from '@/api/candleClient';
import type { ChartCandle } from '@/types/contracts';

import { useCandlesticksStore } from '@/stores/candlesticksStore';

vi.mock('@/api/candleClient', () => ({
  fetchCandles: vi.fn(),
}));

const candle = (timestampMs: number, close = 1.5): ChartCandle => ({
  timestamp_ms: timestampMs,
  time: Math.floor(timestampMs / 1000),
  open: 1,
  high: 2,
  low: 0.5,
  close,
  volume: 100,
});

describe('candlesticks store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(fetchCandles).mockReset();
  });

  it('fetches candles through the typed client and prepends older history when appending', async () => {
    const newest = candle(2_000);
    const oldest = candle(1_000);
    vi.mocked(fetchCandles)
      .mockResolvedValueOnce([newest])
      .mockResolvedValueOnce([oldest]);

    const store = useCandlesticksStore();

    await store.fetch('EURUSD', 'M5', { limit: 1, exchange: 'FX' });
    await store.fetch('EURUSD', 'M5', { endMs: 2_000, limit: 1, append: true, exchange: 'FX' });

    expect(fetchCandles).toHaveBeenNthCalledWith(1, 'EURUSD', 'M5', {
      startMs: null,
      endMs: null,
      limit: 1,
      exchange: 'FX',
    });
    expect(fetchCandles).toHaveBeenNthCalledWith(2, 'EURUSD', 'M5', {
      startMs: null,
      endMs: 2_000,
      limit: 1,
      exchange: 'FX',
    });
    expect(store.data).toEqual([oldest, newest]);
  });

  it('replaces same-time candles, appends future candles, and ignores older candles', () => {
    const store = useCandlesticksStore();
    store.data = [candle(1_000, 1.5)];

    store.updateCandle({ ...candle(1_000, 1.6), type: 'candleUpdate', symbol: 'EURUSD', timeframe: 'M1' });
    expect(store.data).toEqual([candle(1_000, 1.6)]);

    store.updateCandle({ ...candle(2_000, 1.7), type: 'candleUpdate', symbol: 'EURUSD', timeframe: 'M1' });
    expect(store.data).toEqual([candle(1_000, 1.6), candle(2_000, 1.7)]);

    store.updateCandle({ ...candle(500, 1.8), type: 'candleUpdate', symbol: 'EURUSD', timeframe: 'M1' });
    expect(store.data).toEqual([candle(1_000, 1.6), candle(2_000, 1.7)]);
  });

  it('clears chart candle data', () => {
    const store = useCandlesticksStore();
    store.data = [candle(1_000)];

    store.clear();

    expect(store.data).toEqual([]);
  });
});
