import {
  isHistoryDownload,
  isMarketCoverage,
  type HistoryDownload,
  type HistoryDownloadRequest,
  type MarketCoverage,
} from '@/types/historyDownloadContracts';
import { isRecord } from '@/types/transportValues';
import { HttpResponseError, withQuery } from './http';

const BASE_URL = '/api/ingestion/history-downloads';

async function read(response: Response): Promise<unknown> {
  const value: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      isRecord(value) && typeof value.detail === 'string' ? value.detail : null;
    throw new HttpResponseError(
      detail ?? `History request failed (${response.status})`,
      response.status,
    );
  }
  return value;
}

function job(value: unknown): HistoryDownload {
  if (!isHistoryDownload(value))
    throw new Error('Invalid history download response');
  return value;
}

export async function fetchMarketCoverage(
  marketId: number,
): Promise<MarketCoverage> {
  const value = await read(
    await fetch(`/api/data-accessor/markets/id/${marketId}/coverage`),
  );
  if (!isMarketCoverage(value) || value.market_id !== marketId) {
    throw new Error('Invalid market coverage response');
  }
  return value;
}

export async function fetchHistoryDownloads(
  marketId: number,
): Promise<HistoryDownload[]> {
  const value = await read(
    await fetch(withQuery(BASE_URL, { market_id: marketId })),
  );
  if (
    !Array.isArray(value) ||
    !value.every(isHistoryDownload) ||
    value.some((entry) => entry.market_id !== marketId)
  ) {
    throw new Error('Invalid history downloads response');
  }
  return value;
}

export async function requestHistoryDownload(
  request: HistoryDownloadRequest,
): Promise<HistoryDownload> {
  return job(
    await read(
      await fetch(BASE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      }),
    ),
  );
}

export async function changeHistoryDownload(
  id: string,
  action: 'cancel' | 'retry',
): Promise<HistoryDownload> {
  return job(
    await read(
      await fetch(`${BASE_URL}/${encodeURIComponent(id)}/${action}`, {
        method: 'POST',
      }),
    ),
  );
}
