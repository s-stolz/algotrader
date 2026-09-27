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

export interface BacktestRun {
  run_id: string;
  status: BacktestRunStatus;
  submitted_at_ms: number;
  started_at_ms?: number | null;
  completed_at_ms?: number | null;
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
    typeof value.status === 'string' &&
    BACKTEST_RUN_STATUS_SET.has(value.status) &&
    isFiniteNumber(value.submitted_at_ms) &&
    value.submitted_at_ms > 0 &&
    isOptionalNullableNumber(value, 'started_at_ms') &&
    isOptionalNullableNumber(value, 'completed_at_ms') &&
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
