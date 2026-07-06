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
  'succeeded',
  'failed',
] as const;

export type BacktestRunStatus = typeof BACKTEST_RUN_STATUSES[number];
export type BacktestEngine = 'vectorized' | 'event_driven';
export type BacktestDataGranularity = 'bar' | 'tick';
export type BacktestExitReason = 'signal' | 'stop_loss' | 'take_profit';
export type BacktestAllowedDirections = 'long_only' | 'short_only' | 'long_and_short';
export type BacktestTradeDirection = 'long' | 'short';

export interface BacktestStrategyPayload {
  strategy_id: string;
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

export interface BacktestRun {
  run_id: string;
  status: BacktestRunStatus;
  submitted_at_ms: number;
  started_at_ms?: number | null;
  completed_at_ms?: number | null;
  request_schema_version: 2;
  request: BacktestRequestPayload;
  result_schema_version?: number | null;
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
    typeof value.status === 'string' &&
    BACKTEST_RUN_STATUS_SET.has(value.status) &&
    isFiniteNumber(value.submitted_at_ms) &&
    value.submitted_at_ms > 0 &&
    isOptionalNullableNumber(value, 'started_at_ms') &&
    isOptionalNullableNumber(value, 'completed_at_ms') &&
    value.request_schema_version === 2 &&
    isBacktestRequestPayload(value.request) &&
    isOptionalNullableNumber(value, 'result_schema_version') &&
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
  return Array.isArray(value) && value.every(isBacktestClosedTrade);
}
