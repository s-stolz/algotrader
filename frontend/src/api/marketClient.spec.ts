import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  createMarket,
  deleteMarket,
  fetchMarket,
  fetchMarkets,
} from './marketClient';

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

describe('market API client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches and validates markets with optional filters', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([
      {
        symbol_id: 1,
        symbol: 'EURUSD',
        exchange: 'FX',
        market_type: 'forex',
        min_move: 0.00001,
        timezone: 'Europe/Berlin',
      },
    ]));

    await expect(fetchMarkets({ symbol: 'EURUSD', exchange: 'FX' })).resolves.toEqual([
      {
        symbol_id: 1,
        symbol: 'EURUSD',
        exchange: 'FX',
        market_type: 'forex',
        min_move: 0.00001,
        timezone: 'Europe/Berlin',
      },
    ]);
    expect(fetchMock).toHaveBeenCalledWith('/api/data-accessor/markets?symbol=EURUSD&exchange=FX');
  });

  it('rejects invalid market responses before they enter app logic', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse([{ symbol: 'EURUSD' }]));

    await expect(fetchMarkets()).rejects.toThrow('Invalid markets response');
  });

  it('constructs create and delete requests for market flows', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(jsonResponse({ symbol_id: 3, status: 'created' }))
      .mockResolvedValueOnce(jsonResponse({
        symbol_id: 3,
        symbol: 'AAPL',
        exchange: 'NASDAQ',
        market_type: 'stock',
        min_move: 0.01,
        timezone: 'America/New_York',
      }))
      .mockResolvedValueOnce(jsonResponse({ status: 'deleted', deleted_count: 1 }));

    await expect(createMarket({
      symbol: 'AAPL',
      exchange: 'NASDAQ',
      market_type: 'stock',
      min_move: 0.01,
      timezone: 'America/New_York',
    })).resolves.toEqual({ symbol_id: 3, status: 'created' });

    await expect(fetchMarket('AAPL', { exchange: 'NASDAQ' })).resolves.toMatchObject({
      symbol: 'AAPL',
      exchange: 'NASDAQ',
    });

    await expect(deleteMarket('AAPL', { exchange: 'NASDAQ' })).resolves.toEqual({
      status: 'deleted',
      deleted_count: 1,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/data-accessor/markets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: 'AAPL',
        exchange: 'NASDAQ',
        market_type: 'stock',
        min_move: 0.01,
        timezone: 'America/New_York',
      }),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/data-accessor/markets/AAPL?exchange=NASDAQ', {
      method: 'DELETE',
    });
  });
});
