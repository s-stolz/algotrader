import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  fetchAvailableIndicators,
  requestIndicator,
} from '@/api/indicatorClient';

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

describe('indicator API client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches and validates available indicator metadata', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([
      { id: 1, name: 'SMA' },
      { id: 2, name: 'RSI' },
    ]));

    await expect(fetchAvailableIndicators()).resolves.toEqual([
      { id: 1, name: 'SMA' },
      { id: 2, name: 'RSI' },
    ]);
    expect(fetchMock).toHaveBeenCalledWith('/api/indicator-api/indicators');
  });

  it('constructs indicator requests and validates nested response data', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({
      data: {
        indicator_info: {
          id: 1,
          indicator_id: 'sma',
          name: 'SMA',
          overlay: true,
          inputs: [],
          outputs: {
            sma: {
              type: 'line',
              plotOptions: { color: '#fff', lineWidth: 2 },
            },
          },
          parameters: {
            length: { type: 'number', default: 14 },
          },
        },
        indicator_data: [
          { timestamp_ms: 1_700_000_000_000, sma: 1.2 },
        ],
      },
    }));

    await expect(requestIndicator(1, {
      symbol: 'EURUSD',
      timeframe: 'H1',
      limit: 250,
      exchange: 'FX',
    }, {
      parameters: { length: 20 },
    })).resolves.toEqual({
      data: {
        indicator_info: {
          id: 1,
          indicator_id: 'sma',
          name: 'SMA',
          overlay: true,
          inputs: [],
          outputs: {
            sma: {
              type: 'line',
              plotOptions: { color: '#fff', lineWidth: 2 },
            },
          },
          parameters: {
            length: { type: 'number', default: 14 },
          },
        },
        indicator_data: [
          { timestamp_ms: 1_700_000_000_000, sma: 1.2 },
        ],
      },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/indicator-api/indicators/1?symbol=EURUSD&timeframe=H1&exchange=FX&limit=250',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parameters: { length: 20 } }),
      },
    );
  });

  it('rejects invalid indicator responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse({ data: { indicator_data: [] } }));

    await expect(requestIndicator(1, {
      symbol: 'EURUSD',
      timeframe: 'M1',
    })).rejects.toThrow('Invalid indicator response');
  });
});
