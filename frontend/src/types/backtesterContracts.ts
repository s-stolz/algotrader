import {
  type JsonObject,
  type JsonValue,
  isFiniteNumber,
  isRecord,
} from './contracts';

export const BACKTEST_RESULT_SCHEMA_VERSION = 3 as const;

export const BACKTEST_RUN_STATUSES = [
  'queued',
  'running',
  'cancelling',
  'succeeded',
  'failed',
  'cancelled',
] as const;

export type BacktestRunStatus = typeof BACKTEST_RUN_STATUSES[number];
export type BacktestWorkerAvailability = 'healthy' | 'stale' | 'unavailable' | 'faulted';

export interface BacktestQueueEntry {
  entry_type: 'standalone' | 'batch';
  run_id: string | null;
  batch_id: string | null;
  submitted_at_ms: number;
  estimated_position: number;
  next_member_ordinal: number | null;
  outcome_counts: BacktestBatch['outcome_counts'] | null;
}

export interface BacktestQueueSnapshot {
  snapshot_at_ms: number;
  active_run: { run_id: string; started_at_ms: number; batch_id: string | null;
    member_ordinal: number | null } | null;
  last_heartbeat_ms: number | null;
  availability: BacktestWorkerAvailability;
  stale_after_ms: number;
  operational_faults: { code: string; message: string }[];
  queued: BacktestQueueEntry[];
}

export function isBacktestQueueSnapshot(value: unknown): value is BacktestQueueSnapshot {
  if (!isRecord(value) || !isEpochMs(value.snapshot_at_ms) ||
      !isEpochMs(value.stale_after_ms) || value.stale_after_ms === 0 ||
      (value.last_heartbeat_ms !== null && !isEpochMs(value.last_heartbeat_ms)) ||
      !['healthy', 'stale', 'unavailable', 'faulted'].includes(String(value.availability)) ||
      !Array.isArray(value.operational_faults) || !value.operational_faults.every(
        (fault: unknown) => isRecord(fault) && isNonEmptyString(fault.code) &&
          isNonEmptyString(fault.message)) ||
      !Array.isArray(value.queued)) return false;
  if (value.active_run !== null && (!isRecord(value.active_run) ||
      !isNonEmptyString(value.active_run.run_id) ||
      !isEpochMs(value.active_run.started_at_ms) ||
      (value.active_run.batch_id !== null && !isNonEmptyString(value.active_run.batch_id)) ||
      (value.active_run.member_ordinal !== null && !isOrdinal(value.active_run.member_ordinal)) ||
      (value.active_run.batch_id === null) !== (value.active_run.member_ordinal === null))) return false;
  const identities = new Set<string>();
  if (isRecord(value.active_run)) identities.add(value.active_run.batch_id === null
    ? `run:${value.active_run.run_id}` : `batch:${value.active_run.batch_id}`);
  return value.queued.every((entry: unknown, index: number) => {
    if (!isRecord(entry) || !isEpochMs(entry.submitted_at_ms) ||
        entry.estimated_position !== index + 1) return false;
    const isStandalone = entry.entry_type === 'standalone' &&
      isNonEmptyString(entry.run_id) && entry.batch_id === null &&
      entry.next_member_ordinal === null && entry.outcome_counts === null;
    const isBatch = entry.entry_type === 'batch' && entry.run_id === null &&
      isNonEmptyString(entry.batch_id) && isOrdinal(entry.next_member_ordinal) &&
      isBatchOutcomeCounts(entry.outcome_counts);
    if (!isStandalone && !isBatch) return false;
    const identity = isStandalone ? `run:${entry.run_id}` : `batch:${entry.batch_id}`;
    if (identities.has(identity)) return false;
    identities.add(identity);
    return true;
  });
}

function isEpochMs(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}
function isOrdinal(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}
export type BacktestEngine = 'vectorized' | 'event_driven';
export type BacktestDataGranularity = 'bar' | 'tick';
export type BacktestExitReason = 'signal' | 'stop_loss' | 'take_profit';
export type BacktestAllowedDirections = 'long_only' | 'short_only' | 'long_and_short';
export type BacktestTradeDirection = 'long' | 'short';

export interface BacktestStrategyPayload {
  strategy_id: string;
  strategy_version?: number | null;
  parameters: Record<string, JsonValue>;
}

export interface BacktestExecutionPayload {
  signal_timing: 'close';
  fill_timing: 'next_open';
  price_source: 'open' | 'close';
  allow_partial_fills: boolean;
  allowed_directions: BacktestAllowedDirections;
  trade_accounting_policy: 'average_cost';
  gap_policy: 'expire' | 'skip' | 'error';
  intrabar_exit_policy: 'conservative' | 'stop_first' | 'take_profit_first' | 'error';
  commission_bps: number;
  slippage_bps: number;
}

export interface BacktestRequestPayload {
  symbols: string[];
  exchange?: string | null;
  timeframe: string;
  start_ms: number;
  end_ms: number;
  engine: BacktestEngine;
  data_granularity: BacktestDataGranularity;
  initial_capital: number;
  strategy: BacktestStrategyPayload;
  execution: BacktestExecutionPayload;
  persist_result: boolean;
  run_metadata?: JsonObject | null;
}

export type SweepParameterAxis =
  | { mode: 'constant'; value: JsonValue }
  | { mode: 'values'; values: JsonValue[] }
  | { mode: 'range'; start: number; stop: number; step: number };

export interface SweepParameterDraft {
  mode: 'constant' | 'values' | 'range';
  valuesText: string;
  stringValues?: string[];
  choiceIndexes: number[];
  selectedChoiceValues?: JsonValue[];
  includeNull: boolean;
  rangeStart: number | null;
  rangeStop: number | null;
  rangeStep: number | null;
}

export interface SweepDraftState {
  isSweep: boolean;
  marketIds: number[];
  timeframes: string[];
  allowedDirections: BacktestAllowedDirections[];
  parameters: Record<string, SweepParameterDraft>;
}

export interface SweepPreviewRequest extends Omit<BacktestRequestPayload, 'symbols' | 'timeframe' | 'exchange' | 'strategy'> {
  strategy: { strategy_id: string; strategy_version: number };
  markets: number[];
  timeframes: string[];
  parameter_axes: Record<string, SweepParameterAxis>;
  allowed_directions: BacktestAllowedDirections[];
}

export interface SweepPreviewIssue {
  code: string;
  fields: string[];
  message: string;
}

export interface SweepPreviewCandidate {
  candidate_ordinal: number;
  market: { symbol_id: number; symbol: string; exchange: string };
  timeframe: string;
  parameters: Record<string, JsonValue>;
  allowed_directions: BacktestAllowedDirections;
  status: 'ready' | 'excluded';
  member_ordinal?: number;
  request?: BacktestRequestPayload;
  issues?: SweepPreviewIssue[];
}

export interface SweepPreview {
  max_sweep_candidate_count: number;
  normalized_selections: {
    markets: SweepPreviewCandidate['market'][];
    timeframes: string[];
    parameters: Record<string, { mode: string; values: JsonValue[]; range?: {
      start: number; stop: number; step: number;
    } }>;
    allowed_directions: BacktestAllowedDirections[];
  };
  raw_count: number;
  ready_count: number;
  excluded_count: number;
  candidates: SweepPreviewCandidate[];
}

export function isSweepPreview(value: unknown): value is SweepPreview {
  if (!isRecord(value) || !Number.isInteger(value.max_sweep_candidate_count) ||
      !Number.isInteger(value.raw_count) || !Number.isInteger(value.ready_count) ||
      !Number.isInteger(value.excluded_count) || !isRecord(value.normalized_selections) ||
      !Array.isArray(value.normalized_selections.markets) ||
      !value.normalized_selections.markets.every(isSweepMarket) ||
      !Array.isArray(value.normalized_selections.timeframes) ||
      !value.normalized_selections.timeframes.every(isNonEmptyString) ||
      !isRecord(value.normalized_selections.parameters) ||
      !Object.values(value.normalized_selections.parameters).every((axis) => isRecord(axis) &&
        typeof axis.mode === 'string' && Array.isArray(axis.values) &&
        axis.values.length > 0 && axis.values.every(isJsonValue)) ||
      !Array.isArray(value.normalized_selections.allowed_directions) ||
      !value.normalized_selections.allowed_directions.every((direction: unknown) =>
        typeof direction === 'string' && BACKTEST_ALLOWED_DIRECTIONS_SET.has(direction)) ||
      !Array.isArray(value.candidates) || value.candidates.length !== value.raw_count ||
      (value.max_sweep_candidate_count as number) <= 0 ||
      (value.raw_count as number) <= 0 ||
      (value.raw_count as number) > (value.max_sweep_candidate_count as number) ||
      (value.ready_count as number) <= 0 ||
      (value.ready_count as number) + (value.excluded_count as number) !== value.raw_count) return false;
  let ready = 0;
  return value.candidates.every((row: unknown, index: number) => {
    if (!isRecord(row) || row.candidate_ordinal !== index || !isSweepMarket(row.market) ||
        !isNonEmptyString(row.timeframe) ||
        !isRecord(row.parameters) || !Object.values(row.parameters).every(isJsonValue) ||
        typeof row.allowed_directions !== 'string' ||
        !BACKTEST_ALLOWED_DIRECTIONS_SET.has(row.allowed_directions)) return false;
    if (row.status === 'ready') {
      return row.member_ordinal === ready++ && isBacktestRequestPayload(row.request);
    }
    return row.status === 'excluded' && Array.isArray(row.issues) && row.issues.length > 0 &&
      row.issues.every((issue: unknown) => isRecord(issue) && isNonEmptyString(issue.code) &&
        isNonEmptyString(issue.message) && Array.isArray(issue.fields) && issue.fields.every(isNonEmptyString));
  }) && ready === value.ready_count;
}

function isSweepMarket(value: unknown): value is SweepPreviewCandidate['market'] {
  return isRecord(value) && Number.isInteger(value.symbol_id) &&
    isNonEmptyString(value.symbol) && isNonEmptyString(value.exchange);
}

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

export interface EquityReplayPoint {
  timestamp_ms: number;
  equity: number;
  drawdown_pct: number;
}

export interface EquityReplayResponse {
  availability: 'exact' | 'unavailable';
  reason: 'replay_metadata_missing' | 'fingerprint_mismatch' | 'unsupported_replay_shape' | null;
  source_point_count: number;
  returned_point_count: number;
  sampled: boolean;
  equity_curve: EquityReplayPoint[];
}

export function isEquityReplayResponse(value: unknown): value is EquityReplayResponse {
  if (!isRecord(value) || !Array.isArray(value.equity_curve)) return false;
  if (typeof value.source_point_count !== 'number' ||
      !Number.isInteger(value.source_point_count) ||
      typeof value.returned_point_count !== 'number' ||
      !Number.isInteger(value.returned_point_count) ||
      typeof value.sampled !== 'boolean' ||
      value.equity_curve.length !== value.returned_point_count) return false;
  let previousTimestamp = -Infinity;
  for (const point of value.equity_curve) {
    if (!isRecord(point) || typeof point.timestamp_ms !== 'number' ||
        !Number.isInteger(point.timestamp_ms) ||
        point.timestamp_ms <= previousTimestamp ||
        !isFiniteNumber(point.equity) || !isFiniteNumber(point.drawdown_pct) ||
        point.drawdown_pct > 0) return false;
    previousTimestamp = point.timestamp_ms;
  }
  if (value.availability === 'exact') {
    return value.reason === null && value.source_point_count > 0 &&
      value.returned_point_count > 0 &&
      value.returned_point_count <= value.source_point_count &&
      value.sampled === (value.returned_point_count < value.source_point_count);
  }
  return value.availability === 'unavailable' && [
    'replay_metadata_missing', 'fingerprint_mismatch', 'unsupported_replay_shape',
  ].includes(String(value.reason)) && value.source_point_count === 0 &&
    value.returned_point_count === 0 && value.sampled === false;
}

export interface StrategyParameterSchema {
  name: string;
  type: 'bool' | 'int' | 'float' | 'str';
  nullable: boolean;
  required: boolean;
  default?: JsonValue;
  minimum?: number;
  maximum?: number;
  exclusive_minimum?: boolean;
  exclusive_maximum?: boolean;
  choices?: Array<number | string>;
  description?: string;
  display_name?: string;
}

export interface StrategyCatalogEntry {
  strategy_id: string;
  strategy_version: number;
  display_name: string;
  parameters: StrategyParameterSchema[];
}

function matchesParameterType(value: unknown, kind: string, nullable: boolean): boolean {
  if (value === null) return nullable;
  if (kind === 'bool') return typeof value === 'boolean';
  if (kind === 'int') return Number.isInteger(value);
  if (kind === 'float') return isFiniteNumber(value);
  return kind === 'str' && typeof value === 'string';
}

function isStrategyParameterSchema(value: unknown): value is StrategyParameterSchema {
  if (!isRecord(value) || !isNonEmptyString(value.name) ||
      !['bool', 'int', 'float', 'str'].includes(String(value.type)) ||
      typeof value.nullable !== 'boolean' || typeof value.required !== 'boolean') return false;
  const numeric = value.type === 'int' || value.type === 'float';
  return (!('default' in value) || (!value.required &&
    matchesParameterType(value.default, value.type as string, value.nullable))) &&
    (!('minimum' in value) || (numeric && isFiniteNumber(value.minimum))) &&
    (!('maximum' in value) || (numeric && isFiniteNumber(value.maximum))) &&
    (!('exclusive_minimum' in value) ||
      (value.exclusive_minimum === true && isFiniteNumber(value.minimum))) &&
    (!('exclusive_maximum' in value) ||
      (value.exclusive_maximum === true && isFiniteNumber(value.maximum))) &&
    (!('description' in value) || typeof value.description === 'string') &&
    (!('display_name' in value) || typeof value.display_name === 'string') &&
    (!('choices' in value) || (value.type !== 'bool' && Array.isArray(value.choices) &&
      value.choices.every((choice: unknown) =>
        matchesParameterType(choice, value.type as string, false))));
}

export function isStrategyCatalog(value: unknown): value is StrategyCatalogEntry[] {
  return Array.isArray(value) && value.every((entry) => isRecord(entry) &&
    isNonEmptyString(entry.strategy_id) && Number.isInteger(entry.strategy_version) &&
    (entry.strategy_version as number) > 0 && isNonEmptyString(entry.display_name) &&
    Array.isArray(entry.parameters) && entry.parameters.every(isStrategyParameterSchema));
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

export const BACKTEST_BATCH_STATUSES = [
  'queued', 'running', 'pausing', 'paused', 'cancelling', 'completed', 'cancelled',
] as const;
export type BacktestBatchStatus = typeof BACKTEST_BATCH_STATUSES[number];

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
  outcome_counts: Record<BacktestRunStatus | 'cancelling' | 'cancelled', number>;
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

function isBatchOutcomeCounts(value: unknown): value is BacktestBatch['outcome_counts'] {
  return isRecord(value) &&
    ['queued', 'running', 'cancelling', 'succeeded', 'failed', 'cancelled'].every((status) =>
      Number.isSafeInteger(value[status]) && (value[status] as number) >= 0);
}

export function isBacktestBatch(value: unknown): value is BacktestBatch {
  if (!isRecord(value) || !isRecord(value.accepted_definition)) return false;
  const definition = value.accepted_definition;
  return isNonEmptyString(value.batch_id) && isExperimentName(value.name) && isNonEmptyString(value.submission_id) &&
    typeof value.status === 'string' && BACKTEST_BATCH_STATUSES.includes(value.status as BacktestBatchStatus) &&
    Number.isInteger(value.accepted_at_ms) && (value.accepted_at_ms as number) > 0 &&
    (value.started_at_ms === null || isEpochMs(value.started_at_ms)) &&
    (value.completed_at_ms === null || isEpochMs(value.completed_at_ms)) &&
    (value.cancel_requested_at_ms === undefined || value.cancel_requested_at_ms === null ||
      isEpochMs(value.cancel_requested_at_ms)) &&
    (value.cancellation_source === undefined || value.cancellation_source === null ||
      isNonEmptyString(value.cancellation_source)) &&
    (value.cancellation_reason === undefined || value.cancellation_reason === null ||
      isNonEmptyString(value.cancellation_reason)) &&
    (!['cancelling', 'cancelled'].includes(value.status) ||
      (isEpochMs(value.cancel_requested_at_ms) &&
        isNonEmptyString(value.cancellation_source) &&
        isNonEmptyString(value.cancellation_reason))) &&
    (value.status !== 'cancelling' || value.completed_at_ms === null) &&
    (value.status !== 'cancelled' || isEpochMs(value.completed_at_ms)) &&
    (value.active_member_ordinal === null || isOrdinal(value.active_member_ordinal)) &&
    (value.next_member_ordinal === null || isOrdinal(value.next_member_ordinal)) &&
    Number.isInteger(value.lifecycle_revision) && (value.lifecycle_revision as number) >= 0 &&
    value.definition_schema_version === 1 && definition.schema_version === 1 &&
    isJsonObject(definition.shared_request) && isRecord(definition.normalized_selections) &&
    Array.isArray(definition.normalized_selections.markets) &&
    definition.normalized_selections.markets.every(isSweepMarket) &&
    Array.isArray(definition.normalized_selections.timeframes) &&
    definition.normalized_selections.timeframes.every(isNonEmptyString) &&
    isRecord(definition.normalized_selections.parameters) &&
    Object.values(definition.normalized_selections.parameters).every(isJsonObject) &&
    Array.isArray(definition.normalized_selections.allowed_directions) &&
    definition.normalized_selections.allowed_directions.every((direction: unknown) =>
      typeof direction === 'string' && BACKTEST_ALLOWED_DIRECTIONS_SET.has(direction)) &&
    isStrategyCatalog([value.strategy_metadata]) &&
    Number.isInteger(value.raw_count) && Number.isInteger(value.member_count) &&
    Number.isInteger(value.excluded_count) && (value.member_count as number) > 0 &&
    value.raw_count === (value.member_count as number) + (value.excluded_count as number) &&
    value.total_count === value.member_count && Number.isInteger(value.settled_count) &&
    Number.isInteger(value.executed_count) && isBatchOutcomeCounts(value.outcome_counts) &&
    Object.values(value.outcome_counts).reduce((sum: number, count: unknown) =>
      sum + (typeof count === 'number' ? count : 0), 0) === value.total_count &&
    value.settled_count === (value.outcome_counts.succeeded as number) +
      (value.outcome_counts.failed as number) + (value.outcome_counts.cancelled as number) &&
    value.executed_count === (value.outcome_counts.succeeded as number) +
      (value.outcome_counts.failed as number) &&
    value.has_failed_members === ((value.outcome_counts.failed as number) > 0) &&
    Array.isArray(value.markets) && value.markets.every(isNonEmptyString) &&
    Array.isArray(value.exchanges) && value.exchanges.every(isNonEmptyString) &&
    Array.isArray(value.market_contexts) && value.market_contexts.length > 0 &&
    value.market_contexts.every((market: unknown) => isRecord(market) &&
      isNonEmptyString(market.symbol) &&
      (market.exchange === null || isNonEmptyString(market.exchange))) &&
    Array.isArray(value.timeframes) && value.timeframes.length > 0 &&
    value.timeframes.every(isNonEmptyString) &&
    isNonEmptyString(value.strategy_id) &&
    Number.isSafeInteger(value.strategy_version) && (value.strategy_version as number) > 0 &&
    value.strategy_id === (value.strategy_metadata as StrategyCatalogEntry).strategy_id &&
    value.strategy_version === (value.strategy_metadata as StrategyCatalogEntry).strategy_version;
}

export function isBacktestBatchArray(value: unknown): value is BacktestBatch[] {
  return Array.isArray(value) && value.every(isBacktestBatch);
}

export function isBacktestBatchEventArray(value: unknown): value is BacktestBatchEvent[] {
  return Array.isArray(value) && value.every((event: unknown, index: number) => isRecord(event) &&
    isNonEmptyString(event.batch_id) && Number.isInteger(event.revision) &&
    (event.revision as number) >= 0 && isNonEmptyString(event.event_type) &&
    (event.prior_status === null || (typeof event.prior_status === 'string' &&
      BACKTEST_BATCH_STATUSES.includes(event.prior_status as BacktestBatchStatus))) &&
    typeof event.status === 'string' &&
    BACKTEST_BATCH_STATUSES.includes(event.status as BacktestBatchStatus) &&
    isEpochMs(event.occurred_at_ms) &&
    (event.trigger_run_id === null || isNonEmptyString(event.trigger_run_id)) &&
    (event.reason === null || typeof event.reason === 'string') &&
    (!('command_id' in event) || event.command_id === null ||
      isNonEmptyString(event.command_id)) &&
    (index === 0 || (event.revision as number) > value[index - 1].revision));
}

export interface BacktestClosedTrade {
  sequence: number;
  trade_id: string;
  symbol: string;
  trade_direction: BacktestTradeDirection;
  quantity: number;
  entry_timestamp_ms: number;
  entry_price: number;
  exit_timestamp_ms: number;
  exit_price: number;
  realized_pnl: number;
  fees: number;
  exit_reason: BacktestExitReason;
  stop_loss_price: number | null;
  take_profit_price: number | null;
}

export interface BacktestFill {
  sequence: number;
  timestamp_ms: number;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  fees: number;
  exit_reason: BacktestExitReason | null;
}

const BACKTEST_RUN_STATUS_SET: ReadonlySet<string> = new Set(BACKTEST_RUN_STATUSES);
const BACKTEST_ENGINE_SET: ReadonlySet<string> = new Set(['vectorized', 'event_driven']);
const BACKTEST_DATA_GRANULARITY_SET: ReadonlySet<string> = new Set(['bar', 'tick']);
const BACKTEST_ALLOWED_DIRECTIONS_SET: ReadonlySet<string> = new Set([
  'long_only',
  'short_only',
  'long_and_short',
]);
const BACKTEST_PRICE_SOURCE_SET: ReadonlySet<string> = new Set(['open', 'close']);
const BACKTEST_GAP_POLICY_SET: ReadonlySet<string> = new Set(['expire', 'skip', 'error']);
const BACKTEST_INTRABAR_EXIT_POLICY_SET: ReadonlySet<string> = new Set([
  'conservative',
  'stop_first',
  'take_profit_first',
  'error',
]);
const BACKTEST_EXIT_REASON_SET: ReadonlySet<string> = new Set([
  'signal',
  'stop_loss',
  'take_profit',
]);
const BACKTEST_TRADE_DIRECTION_SET: ReadonlySet<string> = new Set(['long', 'short']);

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isJsonValue(value: unknown): value is JsonValue {
  if (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return true;
  }

  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }

  if (isRecord(value)) {
    return Object.values(value).every(isJsonValue);
  }

  return false;
}

function isJsonObject(value: unknown): value is JsonObject {
  return isRecord(value) && Object.values(value).every(isJsonValue);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || isFiniteNumber(value);
}

function isOptionalNullableNumber(value: Record<string, unknown>, key: string): boolean {
  return !(key in value) || value[key] === undefined || isNullableNumber(value[key]);
}

function isOptionalBacktestResultSchemaVersion(value: Record<string, unknown>): boolean {
  return !('result_schema_version' in value) ||
    value.result_schema_version === undefined ||
    value.result_schema_version === null ||
    value.result_schema_version === 1 ||
    value.result_schema_version === 2 ||
    value.result_schema_version === BACKTEST_RESULT_SCHEMA_VERSION;
}

function isOptionalNullableString(value: Record<string, unknown>, key: string): boolean {
  return !(key in value) || value[key] === undefined || isNullableString(value[key]);
}

function isOptionalNullableJsonObject(value: Record<string, unknown>, key: string): boolean {
  return !(key in value) ||
    value[key] === undefined ||
    value[key] === null ||
    isJsonObject(value[key]);
}

function isBacktestStrategyPayload(value: unknown): value is BacktestStrategyPayload {
  return (
    isRecord(value) &&
    isNonEmptyString(value.strategy_id) &&
    (!('strategy_version' in value) || value.strategy_version === null || (
      Number.isInteger(value.strategy_version) && (value.strategy_version as number) > 0
    )) &&
    isRecord(value.parameters) &&
    Object.values(value.parameters).every(isJsonValue)
  );
}

function isBacktestExecutionPayload(value: unknown): value is BacktestExecutionPayload {
  return (
    isRecord(value) &&
    value.signal_timing === 'close' &&
    value.fill_timing === 'next_open' &&
    typeof value.price_source === 'string' &&
    BACKTEST_PRICE_SOURCE_SET.has(value.price_source) &&
    typeof value.allow_partial_fills === 'boolean' &&
    !('allow_short' in value) &&
    typeof value.allowed_directions === 'string' &&
    BACKTEST_ALLOWED_DIRECTIONS_SET.has(value.allowed_directions) &&
    value.trade_accounting_policy === 'average_cost' &&
    typeof value.gap_policy === 'string' &&
    BACKTEST_GAP_POLICY_SET.has(value.gap_policy) &&
    typeof value.intrabar_exit_policy === 'string' &&
    BACKTEST_INTRABAR_EXIT_POLICY_SET.has(value.intrabar_exit_policy) &&
    isFiniteNumber(value.commission_bps) &&
    value.commission_bps >= 0 &&
    isFiniteNumber(value.slippage_bps) &&
    value.slippage_bps >= 0
  );
}

export function isBacktestRequestPayload(value: unknown): value is BacktestRequestPayload {
  if (!isRecord(value)) {
    return false;
  }

  return (
    Array.isArray(value.symbols) &&
    value.symbols.every(isNonEmptyString) &&
    isOptionalNullableString(value, 'exchange') &&
    isNonEmptyString(value.timeframe) &&
    isFiniteNumber(value.start_ms) &&
    value.start_ms > 0 &&
    isFiniteNumber(value.end_ms) &&
    value.end_ms > value.start_ms &&
    typeof value.engine === 'string' &&
    BACKTEST_ENGINE_SET.has(value.engine) &&
    typeof value.data_granularity === 'string' &&
    BACKTEST_DATA_GRANULARITY_SET.has(value.data_granularity) &&
    isFiniteNumber(value.initial_capital) &&
    value.initial_capital > 0 &&
    isBacktestStrategyPayload(value.strategy) &&
    isBacktestExecutionPayload(value.execution) &&
    typeof value.persist_result === 'boolean' &&
    isOptionalNullableJsonObject(value, 'run_metadata')
  );
}

export function isBacktestRun(value: unknown): value is BacktestRun {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isNonEmptyString(value.run_id) &&
    isExperimentName(value.name) &&
    (!('batch_id' in value) || value.batch_id === null || isNonEmptyString(value.batch_id)) &&
    (!('member_ordinal' in value) || value.member_ordinal === null ||
      (Number.isInteger(value.member_ordinal) && (value.member_ordinal as number) >= 0)) &&
    ((value.batch_id == null && value.member_ordinal == null) ||
      (isNonEmptyString(value.batch_id) && Number.isInteger(value.member_ordinal))) &&
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
    (value.request_schema_version === 2 || value.request_schema_version === 3) &&
    (value.request_schema_version !== 3 || (isRecord(value.request) &&
      isRecord(value.request.strategy) && Number.isInteger(value.request.strategy.strategy_version))) &&
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

export function isBacktestClosedTrade(value: unknown): value is BacktestClosedTrade {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isFiniteNumber(value.sequence) &&
    value.sequence >= 0 &&
    isNonEmptyString(value.trade_id) &&
    isNonEmptyString(value.symbol) &&
    typeof value.trade_direction === 'string' &&
    BACKTEST_TRADE_DIRECTION_SET.has(value.trade_direction) &&
    isFiniteNumber(value.quantity) &&
    value.quantity > 0 &&
    isFiniteNumber(value.entry_timestamp_ms) &&
    value.entry_timestamp_ms > 0 &&
    isFiniteNumber(value.entry_price) &&
    isFiniteNumber(value.exit_timestamp_ms) &&
    value.exit_timestamp_ms >= value.entry_timestamp_ms &&
    isFiniteNumber(value.exit_price) &&
    isFiniteNumber(value.realized_pnl) &&
    isFiniteNumber(value.fees) &&
    typeof value.exit_reason === 'string' &&
    BACKTEST_EXIT_REASON_SET.has(value.exit_reason) &&
    'stop_loss_price' in value &&
    isNullableNumber(value.stop_loss_price) &&
    'take_profit_price' in value &&
    isNullableNumber(value.take_profit_price)
  );
}

export function isBacktestClosedTradeArray(value: unknown): value is BacktestClosedTrade[] {
  return Array.isArray(value) && value.every(isBacktestClosedTrade) &&
    value.every((trade, index) => index === 0 || trade.sequence > value[index - 1].sequence);
}

export function isBacktestFill(value: unknown): value is BacktestFill {
  if (!isRecord(value)) return false;
  return Number.isInteger(value.sequence) && (value.sequence as number) >= 0 &&
    isFiniteNumber(value.timestamp_ms) && value.timestamp_ms > 0 &&
    isNonEmptyString(value.symbol) &&
    (value.side === 'buy' || value.side === 'sell') &&
    isFiniteNumber(value.quantity) && value.quantity > 0 &&
    isFiniteNumber(value.price) &&
    isFiniteNumber(value.fees) &&
    (value.exit_reason === null ||
      (typeof value.exit_reason === 'string' && BACKTEST_EXIT_REASON_SET.has(value.exit_reason)));
}

export function isBacktestFillArray(value: unknown): value is BacktestFill[] {
  return Array.isArray(value) && value.every(isBacktestFill) &&
    value.every((fill, index) => index === 0 || fill.sequence > value[index - 1].sequence);
}

export function normalizeExperimentName(value: string | null | undefined): string | null {
  if (value == null) return null;
  const name = value.replace(/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu, '');
  if (!name) return null;
  if (/[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/u.test(value)) {
    throw new Error('Experiment name must be single-line.');
  }
  if ([...name].length > 120) throw new Error('Experiment name must have at most 120 characters.');
  return name || null;
}

function isExperimentName(value: unknown): boolean {
  if (value == null) return true;
  if (typeof value !== 'string') return false;
  try { return normalizeExperimentName(value) === value; } catch { return false; }
}

export type BacktestCreationRequest = BacktestRequestPayload & { name?: string | null };
