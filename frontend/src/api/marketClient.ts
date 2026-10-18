import {
  type DeleteResponse,
  type Market,
  type MarketCreatePayload,
  type MarketCreateResponse,
  isDeleteResponse,
  isMarket,
  isMarketArray,
  isMarketCreateResponse,
} from '@/types/contracts';

import { parseJsonResponse, withQuery } from './http';

const MARKETS_BASE_URL = '/api/data-accessor/markets';

export interface MarketFilter {
  symbol?: string | null;
  exchange?: string | null;
}

export async function fetchMarkets(filters: MarketFilter = {}): Promise<Market[]> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(MARKETS_BASE_URL, {
      symbol: filters.symbol,
      exchange: filters.exchange,
    })),
    'Failed to fetch markets',
  );

  if (!isMarketArray(payload)) {
    throw new Error('Invalid markets response');
  }

  return payload;
}

export async function fetchMarket(symbol: string, filters: Omit<MarketFilter, 'symbol'> = {}): Promise<Market> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(`${MARKETS_BASE_URL}/${encodeURIComponent(symbol)}`, {
      exchange: filters.exchange,
    })),
    'Failed to fetch market',
  );

  if (!isMarket(payload)) {
    throw new Error('Invalid market response');
  }

  return payload;
}

export async function createMarket(payload: MarketCreatePayload): Promise<MarketCreateResponse> {
  const responsePayload = await parseJsonResponse(
    await fetch(MARKETS_BASE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
    'Failed to create market',
  );

  if (!isMarketCreateResponse(responsePayload)) {
    throw new Error('Invalid market create response');
  }

  return responsePayload;
}

export async function deleteMarket(symbol: string, filters: Omit<MarketFilter, 'symbol'> = {}): Promise<DeleteResponse> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(`${MARKETS_BASE_URL}/${encodeURIComponent(symbol)}`, {
      exchange: filters.exchange,
    }), {
      method: 'DELETE',
    }),
    'Failed to delete market',
  );

  if (!isDeleteResponse(payload)) {
    throw new Error('Invalid market delete response');
  }

  return payload;
}
