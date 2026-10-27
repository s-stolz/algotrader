import {
  type JsonObject,
  isRecord,
  isFiniteNumber,
  isNonEmptyString,
} from '../transportValues';
import {
  type BacktestEngine,
  type BacktestRequestPayload,
  isBacktestRequestPayload,
} from './requests';
import { BACKTEST_RESULT_SCHEMA_VERSION } from './results';
import {
  isOptionalNullableNumber,
  isOptionalNullableString,
  isOptionalNullableJsonObject,
} from './validation';

export const BACKTEST_RUN_STATUSES = [
  'queued',
  'running',
  'cancelling',
  'succeeded',
  'failed',
  'cancelled',
] as const;

export type BacktestRunStatus = (typeof BACKTEST_RUN_STATUSES)[number];

export interface BacktestRun {
  run_id: string;
  name?: string | null;
  batch_id?: string;
  member_ordinal?: number;
  status: BacktestRunStatus;
  submitted_at_ms: number;
  started_at_ms?: number | null;
  completed_at_ms?: number | null;
  cancel_requested_at_ms?: number | null;
  cancellation_source?: string | null;
  cancellation_reason?: string | null;
  request_schema_version: 2 | 3;
  request: BacktestRequestPayload;
  result_schema_version?: 1 | 2 | typeof BACKTEST_RESULT_SCHEMA_VERSION | null;
  metrics?: JsonObject | null;
  diagnostics?: JsonObject | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface BacktestRunListQuery {
  status?: BacktestRunStatus | null;
  symbol?: string | null;
  timeframe?: string | null;
  strategy?: string | null;
  engine?: BacktestEngine | null;
  submittedFromMs?: number | null;
  submittedToMs?: number | null;
  membership?: 'standalone' | 'batch' | null;
  batchId?: string | null;
}

const BACKTEST_RUN_STATUS_SET: ReadonlySet<string> = new Set(
  BACKTEST_RUN_STATUSES,
);

function isOptionalBacktestResultSchemaVersion(
  value: Record<string, unknown>,
): boolean {
  return (
    !('result_schema_version' in value) ||
    value.result_schema_version === undefined ||
    value.result_schema_version === null ||
    value.result_schema_version === 1 ||
    value.result_schema_version === 2 ||
    value.result_schema_version === BACKTEST_RESULT_SCHEMA_VERSION
  );
}

export function isBacktestRun(value: unknown): value is BacktestRun {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isNonEmptyString(value.run_id) &&
    isExperimentName(value.name) &&
    (!('batch_id' in value) ||
      value.batch_id === null ||
      isNonEmptyString(value.batch_id)) &&
    (!('member_ordinal' in value) ||
      value.member_ordinal === null ||
      (Number.isInteger(value.member_ordinal) &&
        (value.member_ordinal as number) >= 0)) &&
    ((value.batch_id == null && value.member_ordinal == null) ||
      (isNonEmptyString(value.batch_id) &&
        Number.isInteger(value.member_ordinal))) &&
    typeof value.status === 'string' &&
    BACKTEST_RUN_STATUS_SET.has(value.status) &&
    isFiniteNumber(value.submitted_at_ms) &&
    value.submitted_at_ms > 0 &&
    isOptionalNullableNumber(value, 'started_at_ms') &&
    isOptionalNullableNumber(value, 'completed_at_ms') &&
    isOptionalNullableNumber(value, 'cancel_requested_at_ms') &&
    isOptionalNullableString(value, 'cancellation_source') &&
    isOptionalNullableString(value, 'cancellation_reason') &&
    (!['cancelling', 'cancelled'].includes(value.status as string) ||
      (isFiniteNumber(value.cancel_requested_at_ms) &&
        isNonEmptyString(value.cancellation_source) &&
        isNonEmptyString(value.cancellation_reason))) &&
    (value.request_schema_version === 2 ||
      value.request_schema_version === 3) &&
    (value.request_schema_version !== 3 ||
      (isRecord(value.request) &&
        isRecord(value.request.strategy) &&
        Number.isInteger(value.request.strategy.strategy_version))) &&
    isBacktestRequestPayload(value.request) &&
    isOptionalBacktestResultSchemaVersion(value) &&
    isOptionalNullableJsonObject(value, 'metrics') &&
    isOptionalNullableJsonObject(value, 'diagnostics') &&
    isOptionalNullableString(value, 'error_code') &&
    isOptionalNullableString(value, 'error_message')
  );
}

export function isBacktestRunArray(value: unknown): value is BacktestRun[] {
  return Array.isArray(value) && value.every(isBacktestRun);
}

export function normalizeExperimentName(
  value: string | null | undefined,
): string | null {
  if (value == null) return null;
  const name = value.replace(
    /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu,
    '',
  );
  if (!name) return null;
  if (/[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/u.test(value)) {
    throw new Error('Experiment name must be single-line.');
  }
  if ([...name].length > 120)
    throw new Error('Experiment name must have at most 120 characters.');
  return name || null;
}

export function isExperimentName(value: unknown): boolean {
  if (value == null) return true;
  if (typeof value !== 'string') return false;
  try {
    return normalizeExperimentName(value) === value;
  } catch {
    return false;
  }
}
