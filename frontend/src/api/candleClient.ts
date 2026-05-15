import {
  type CandleBatchPayload,
  type CandleBatchResponse,
  type CandleFetchOptions,
  type ChartCandle,
  type DeleteResponse,
  isCandleArray,
  isCandleBatchResponse,
  isDeleteResponse,
  toChartCandle,
} from '@/types/contracts';

import { parseJsonResponse, withQuery } from './http';

const CANDLES_BASE_URL = '/api/data-accessor/candles';

export async function fetchCandles(
  symbol: string,
  timeframe: string,
  options: CandleFetchOptions = {},
): Promise<ChartCandle[]> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(`${CANDLES_BASE_URL}/${encodeURIComponent(symbol)}`, {
      timeframe,
      start_ms: options.startMs,
      end_ms: options.endMs,
      limit: options.limit,
      exchange: options.exchange,
    })),
    'Failed to fetch candles',
  );

  if (!isCandleArray(payload)) {
    throw new Error('Invalid candles response');
  }

  return payload.map(toChartCandle);
}

export async function uploadCandleBatch(payload: CandleBatchPayload): Promise<CandleBatchResponse> {
  const responsePayload = await parseJsonResponse(
    await fetch(CANDLES_BASE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
    'Failed to upload candle batch',
  );

  if (!isCandleBatchResponse(responsePayload)) {
    throw new Error('Invalid candle upload response');
  }

  return responsePayload;
}

export async function deleteCandles(
  symbol: string,
  options: Pick<CandleFetchOptions, 'exchange'> = {},
): Promise<DeleteResponse> {
  const payload = await parseJsonResponse(
    await fetch(withQuery(`${CANDLES_BASE_URL}/${encodeURIComponent(symbol)}`, {
      exchange: options.exchange,
    }), {
      method: 'DELETE',
    }),
    'Failed to delete candles',
  );

  if (!isDeleteResponse(payload)) {
    throw new Error('Invalid candle delete response');
  }

  return payload;
}
