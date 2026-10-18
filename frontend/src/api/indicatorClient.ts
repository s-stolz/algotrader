import {
  type AvailableIndicator,
  type IndicatorQuery,
  type IndicatorRequestBody,
  type IndicatorResponse,
  isAvailableIndicatorArray,
  isIndicatorResponse,
} from '@/types/contracts';

import { parseJsonResponse, withQuery } from './http';

const INDICATORS_BASE_URL = '/api/indicator-api/indicators';

export async function fetchAvailableIndicators(): Promise<AvailableIndicator[]> {
  const payload = await parseJsonResponse(
    await fetch(INDICATORS_BASE_URL),
    'Failed to fetch indicators',
  );

  if (!isAvailableIndicatorArray(payload)) {
    throw new Error('Invalid indicators response');
  }

  return payload;
}

export async function requestIndicator(
  indicatorId: number,
  query: IndicatorQuery,
  body: IndicatorRequestBody = {},
): Promise<IndicatorResponse> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(`${INDICATORS_BASE_URL}/${encodeURIComponent(String(indicatorId))}`, {
      symbol: query.symbol,
      timeframe: query.timeframe,
      exchange: query.exchange,
      start_ms: query.startMs,
      end_ms: query.endMs,
      limit: query.limit,
    }), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
    'Failed to request indicator',
  );

  if (!isIndicatorResponse(payload)) {
    throw new Error('Invalid indicator response');
  }

  return payload;
}
