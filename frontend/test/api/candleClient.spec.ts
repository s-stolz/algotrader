import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  deleteCandles,
  fetchCandles,
  uploadCandleBatch,
} from '@/api/candleClient';

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

describe('candle API client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('constructs candle query URLs and maps API candles to chart candles', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([
      {
        timestamp_ms: 1_700_000_000_000,
        open: 1.1,
        high: 1.3,
        low: 1,
        close: 1.2,
        volume: 50,
      },
    ]));

    await expect(fetchCandles('EURUSD', 'M5', {
      startMs: 1000,
      endMs: 2000,
      limit: 10,
      exchange: 'FX',
    })).resolves.toEqual([
      {
        timestamp_ms: 1_700_000_000_000,
        time: 1_700_000_000,
        open: 1.1,
        high: 1.3,
        low: 1,
        close: 1.2,
        volume: 50,
      },
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/data-accessor/candles/EURUSD?timeframe=M5&start_ms=1000&end_ms=2000&limit=10&exchange=FX',
    );
  });

  it('rejects malformed candle payloads and non-OK uploads clearly', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse([{ timestamp_ms: 'bad' }]));
    await expect(fetchCandles('EURUSD', 'M1')).rejects.toThrow('Invalid candles response');

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(jsonResponse({ detail: 'bad' }, {
      status: 422,
      statusText: 'Unprocessable Entity',
    }));
    await expect(uploadCandleBatch({
      symbol: 'EURUSD',
      exchange: 'FX',
      candles: [],
    })).rejects.toThrow('Failed to upload candle batch: Unprocessable Entity');
  });

  it('constructs upload and delete requests', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ status: 'ok', added_candles: 1, total_candles: 1 }))
      .mockResolvedValueOnce(jsonResponse({ status: 'deleted', deleted_count: 4 }));

    await expect(uploadCandleBatch({
      symbol: 'EURUSD',
      exchange: 'FX',
      candles: [{
        timestamp_ms: 1_700_000_000_000,
        open: 1,
        high: 2,
        low: 0.5,
        close: 1.5,
        volume: 100,
      }],
    })).resolves.toEqual({ status: 'ok', added_candles: 1, total_candles: 1 });

    await expect(deleteCandles('EURUSD', { exchange: 'FX' })).resolves.toEqual({
      status: 'deleted',
      deleted_count: 4,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/data-accessor/candles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: 'EURUSD',
        exchange: 'FX',
        candles: [{
          timestamp_ms: 1_700_000_000_000,
          open: 1,
          high: 2,
          low: 0.5,
          close: 1.5,
          volume: 100,
        }],
      }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/data-accessor/candles/EURUSD?exchange=FX', {
      method: 'DELETE',
    });
  });
});
