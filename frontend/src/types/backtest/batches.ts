import {
  type JsonObject,
  isRecord,
  isNonEmptyString,
  isJsonObject,
} from '../transportValues';
import { type BacktestRunStatus, isExperimentName } from './history';
import {
  type StrategyCatalogEntry,
  BACKTEST_ALLOWED_DIRECTIONS_SET,
  isStrategyCatalog,
} from './requests';
import { type SweepPreview, isSweepMarket } from './sweeps';
import { isEpochMs, isOrdinal } from './validation';

export const BACKTEST_BATCH_STATUSES = [
  'queued',
  'running',
  'pausing',
  'paused',
  'cancelling',
  'completed',
  'cancelled',
] as const;

export type BacktestBatchStatus = (typeof BACKTEST_BATCH_STATUSES)[number];

export interface BacktestBatch {
  batch_id: string;
  name?: string | null;
  submission_id: string;
  status: BacktestBatchStatus;
  accepted_at_ms: number;
  started_at_ms: number | null;
  completed_at_ms: number | null;
  cancel_requested_at_ms?: number | null;
  cancellation_source?: string | null;
  cancellation_reason?: string | null;
  active_member_ordinal: number | null;
  next_member_ordinal: number | null;
  lifecycle_revision: number;
  definition_schema_version: 1;
  accepted_definition: {
    schema_version: 1;
    shared_request: JsonObject;
    normalized_selections: SweepPreview['normalized_selections'];
  };
  strategy_metadata: StrategyCatalogEntry;
  raw_count: number;
  member_count: number;
  excluded_count: number;
  total_count: number;
  settled_count: number;
  executed_count: number;
  outcome_counts: Record<
    BacktestRunStatus | 'cancelling' | 'cancelled',
    number
  >;
  has_failed_members: boolean;
  markets: string[];
  exchanges: string[];
  market_contexts: { symbol: string; exchange: string | null }[];
  timeframes: string[];
  strategy_id: string;
  strategy_version: number;
}

export interface BacktestBatchEvent {
  batch_id: string;
  revision: number;
  event_type: string;
  prior_status: BacktestBatchStatus | null;
  status: BacktestBatchStatus;
  occurred_at_ms: number;
  trigger_run_id: string | null;
  reason: string | null;
  command_id?: string | null;
}

export function isBatchOutcomeCounts(
  value: unknown,
): value is BacktestBatch['outcome_counts'] {
  return (
    isRecord(value) &&
    [
      'queued',
      'running',
      'cancelling',
      'succeeded',
      'failed',
      'cancelled',
    ].every(
      (status) =>
        Number.isSafeInteger(value[status]) && (value[status] as number) >= 0,
    )
  );
}

export function isBacktestBatch(value: unknown): value is BacktestBatch {
  if (!isRecord(value) || !isRecord(value.accepted_definition)) return false;
  const definition = value.accepted_definition;
  return (
    isNonEmptyString(value.batch_id) &&
    isExperimentName(value.name) &&
    isNonEmptyString(value.submission_id) &&
    typeof value.status === 'string' &&
    BACKTEST_BATCH_STATUSES.includes(value.status as BacktestBatchStatus) &&
    Number.isInteger(value.accepted_at_ms) &&
    (value.accepted_at_ms as number) > 0 &&
    (value.started_at_ms === null || isEpochMs(value.started_at_ms)) &&
    (value.completed_at_ms === null || isEpochMs(value.completed_at_ms)) &&
    (value.cancel_requested_at_ms === undefined ||
      value.cancel_requested_at_ms === null ||
      isEpochMs(value.cancel_requested_at_ms)) &&
    (value.cancellation_source === undefined ||
      value.cancellation_source === null ||
      isNonEmptyString(value.cancellation_source)) &&
    (value.cancellation_reason === undefined ||
      value.cancellation_reason === null ||
      isNonEmptyString(value.cancellation_reason)) &&
    (!['cancelling', 'cancelled'].includes(value.status) ||
      (isEpochMs(value.cancel_requested_at_ms) &&
        isNonEmptyString(value.cancellation_source) &&
        isNonEmptyString(value.cancellation_reason))) &&
    (value.status !== 'cancelling' || value.completed_at_ms === null) &&
    (value.status !== 'cancelled' || isEpochMs(value.completed_at_ms)) &&
    (value.active_member_ordinal === null ||
      isOrdinal(value.active_member_ordinal)) &&
    (value.next_member_ordinal === null ||
      isOrdinal(value.next_member_ordinal)) &&
    Number.isInteger(value.lifecycle_revision) &&
    (value.lifecycle_revision as number) >= 0 &&
    value.definition_schema_version === 1 &&
    definition.schema_version === 1 &&
    isJsonObject(definition.shared_request) &&
    isRecord(definition.normalized_selections) &&
    Array.isArray(definition.normalized_selections.markets) &&
    definition.normalized_selections.markets.every(isSweepMarket) &&
    Array.isArray(definition.normalized_selections.timeframes) &&
    definition.normalized_selections.timeframes.every(isNonEmptyString) &&
    isRecord(definition.normalized_selections.parameters) &&
    Object.values(definition.normalized_selections.parameters).every(
      isJsonObject,
    ) &&
    Array.isArray(definition.normalized_selections.allowed_directions) &&
    definition.normalized_selections.allowed_directions.every(
      (direction: unknown) =>
        typeof direction === 'string' &&
        BACKTEST_ALLOWED_DIRECTIONS_SET.has(direction),
    ) &&
    isStrategyCatalog([value.strategy_metadata]) &&
    Number.isInteger(value.raw_count) &&
    Number.isInteger(value.member_count) &&
    Number.isInteger(value.excluded_count) &&
    (value.member_count as number) > 0 &&
    value.raw_count ===
      (value.member_count as number) + (value.excluded_count as number) &&
    value.total_count === value.member_count &&
    Number.isInteger(value.settled_count) &&
    Number.isInteger(value.executed_count) &&
    isBatchOutcomeCounts(value.outcome_counts) &&
    Object.values(value.outcome_counts).reduce(
      (sum: number, count: unknown) =>
        sum + (typeof count === 'number' ? count : 0),
      0,
    ) === value.total_count &&
    value.settled_count ===
      (value.outcome_counts.succeeded as number) +
        (value.outcome_counts.failed as number) +
        (value.outcome_counts.cancelled as number) &&
    value.executed_count ===
      (value.outcome_counts.succeeded as number) +
        (value.outcome_counts.failed as number) &&
    value.has_failed_members === (value.outcome_counts.failed as number) > 0 &&
    Array.isArray(value.markets) &&
    value.markets.every(isNonEmptyString) &&
    Array.isArray(value.exchanges) &&
    value.exchanges.every(isNonEmptyString) &&
    Array.isArray(value.market_contexts) &&
    value.market_contexts.length > 0 &&
    value.market_contexts.every(
      (market: unknown) =>
        isRecord(market) &&
        isNonEmptyString(market.symbol) &&
        (market.exchange === null || isNonEmptyString(market.exchange)),
    ) &&
    Array.isArray(value.timeframes) &&
    value.timeframes.length > 0 &&
    value.timeframes.every(isNonEmptyString) &&
    isNonEmptyString(value.strategy_id) &&
    Number.isSafeInteger(value.strategy_version) &&
    (value.strategy_version as number) > 0 &&
    value.strategy_id ===
      (value.strategy_metadata as StrategyCatalogEntry).strategy_id &&
    value.strategy_version ===
      (value.strategy_metadata as StrategyCatalogEntry).strategy_version
  );
}

export function isBacktestBatchArray(value: unknown): value is BacktestBatch[] {
  return Array.isArray(value) && value.every(isBacktestBatch);
}

export function isBacktestBatchEventArray(
  value: unknown,
): value is BacktestBatchEvent[] {
  return (
    Array.isArray(value) &&
    value.every(
      (event: unknown, index: number) =>
        isRecord(event) &&
        isNonEmptyString(event.batch_id) &&
        Number.isInteger(event.revision) &&
        (event.revision as number) >= 0 &&
        isNonEmptyString(event.event_type) &&
        (event.prior_status === null ||
          (typeof event.prior_status === 'string' &&
            BACKTEST_BATCH_STATUSES.includes(
              event.prior_status as BacktestBatchStatus,
            ))) &&
        typeof event.status === 'string' &&
        BACKTEST_BATCH_STATUSES.includes(event.status as BacktestBatchStatus) &&
        isEpochMs(event.occurred_at_ms) &&
        (event.trigger_run_id === null ||
          isNonEmptyString(event.trigger_run_id)) &&
        (event.reason === null || typeof event.reason === 'string') &&
        (!('command_id' in event) ||
          event.command_id === null ||
          isNonEmptyString(event.command_id)) &&
        (index === 0 || (event.revision as number) > value[index - 1].revision),
    )
  );
}
