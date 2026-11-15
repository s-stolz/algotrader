import { isRecord, isFiniteNumber, isNonEmptyString } from './transportValues';

export interface MarketCoverage {
  market_id: number;
  oldest_timestamp_ms: number | null;
  latest_timestamp_ms: number | null;
  candle_count: number;
}

export type HistoryDownloadStatus =
  'queued' | 'downloading' | 'completed' | 'failed' | 'cancelled';

export interface HistoryDownload {
  id: string;
  market_id: number;
  status: HistoryDownloadStatus;
  start_ms: number | null;
  candle_count: number | null;
  end_exclusive_ms: number;
  cursor_ms: number;
  fetched_count: number;
  inserted_count: number;
  revision: number;
  created_at: string;
  updated_at: string;
  failure_reason: string | null;
  availability_reason: string | null;
  cancel_requested?: boolean;
}

export type HistoryDownloadRequest = {
  request_id: string;
  market_id: number;
} & ({ start_date: string } | { candle_count: number });

export interface HistoryDownloadChanged {
  type: 'historyDownloadChanged';
  market_id: number;
  job_id: string;
  revision: number;
}

export interface HistoryDownloadsConnection {
  type: 'historyDownloadsConnection';
  market_id: number;
  connected: boolean;
}

const statuses = new Set([
  'queued',
  'downloading',
  'completed',
  'failed',
  'cancelled',
]);
const nullableNumber = (value: unknown) =>
  value === null || isFiniteNumber(value);
const nullableString = (value: unknown) =>
  value === null || typeof value === 'string';
const positiveInteger = (value: unknown) =>
  Number.isInteger(value) && Number(value) > 0;
const nonnegativeInteger = (value: unknown) =>
  Number.isInteger(value) && Number(value) >= 0;

export function isMarketCoverage(value: unknown): value is MarketCoverage {
  return (
    isRecord(value) &&
    positiveInteger(value.market_id) &&
    nullableNumber(value.oldest_timestamp_ms) &&
    nullableNumber(value.latest_timestamp_ms) &&
    nonnegativeInteger(value.candle_count)
  );
}

export function isHistoryDownload(value: unknown): value is HistoryDownload {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    positiveInteger(value.market_id) &&
    statuses.has(String(value.status)) &&
    nullableNumber(value.start_ms) &&
    nullableNumber(value.candle_count) &&
    isFiniteNumber(value.end_exclusive_ms) &&
    isFiniteNumber(value.cursor_ms) &&
    ['fetched_count', 'inserted_count', 'revision'].every((key) =>
      nonnegativeInteger(value[key]),
    ) &&
    isNonEmptyString(value.created_at) &&
    isNonEmptyString(value.updated_at) &&
    nullableString(value.failure_reason) &&
    nullableString(value.availability_reason) &&
    (value.cancel_requested === undefined ||
      typeof value.cancel_requested === 'boolean')
  );
}

export function isHistoryEvent(
  value: unknown,
): value is HistoryDownloadChanged | HistoryDownloadsConnection {
  if (!isRecord(value) || !positiveInteger(value.market_id)) return false;
  if (value.type === 'historyDownloadsConnection')
    return typeof value.connected === 'boolean';
  return (
    value.type === 'historyDownloadChanged' &&
    isNonEmptyString(value.job_id) &&
    nonnegativeInteger(value.revision)
  );
}

export function isDownloadActive(job: HistoryDownload): boolean {
  return job.status === 'queued' || job.status === 'downloading';
}
