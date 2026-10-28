import {
  type JsonObject,
  type JsonValue,
  isRecord,
  isFiniteNumber,
  isNonEmptyString,
  isJsonValue,
} from '../transportValues';
import {
  isOptionalNullableString,
  isOptionalNullableJsonObject,
} from './validation';

export type BacktestEngine = 'vectorized' | 'event_driven';

export type BacktestDataGranularity = 'bar' | 'tick';

export type BacktestExitReason = 'signal' | 'stop_loss' | 'take_profit';

export type BacktestAllowedDirections =
  | 'long_only'
  | 'short_only'
  | 'long_and_short';

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
  intrabar_exit_policy:
    | 'conservative'
    | 'stop_first'
    | 'take_profit_first'
    | 'error';
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

function matchesParameterType(
  value: unknown,
  kind: string,
  nullable: boolean,
): boolean {
  if (value === null) return nullable;
  if (kind === 'bool') return typeof value === 'boolean';
  if (kind === 'int') return Number.isInteger(value);
  if (kind === 'float') return isFiniteNumber(value);
  return kind === 'str' && typeof value === 'string';
}

function isStrategyParameterSchema(
  value: unknown,
): value is StrategyParameterSchema {
  if (
    !isRecord(value) ||
    !isNonEmptyString(value.name) ||
    !['bool', 'int', 'float', 'str'].includes(String(value.type)) ||
    typeof value.nullable !== 'boolean' ||
    typeof value.required !== 'boolean'
  )
    return false;
  const numeric = value.type === 'int' || value.type === 'float';
  return (
    (!('default' in value) ||
      (!value.required &&
        matchesParameterType(
          value.default,
          value.type as string,
          value.nullable,
        ))) &&
    (!('minimum' in value) || (numeric && isFiniteNumber(value.minimum))) &&
    (!('maximum' in value) || (numeric && isFiniteNumber(value.maximum))) &&
    (!('exclusive_minimum' in value) ||
      (value.exclusive_minimum === true && isFiniteNumber(value.minimum))) &&
    (!('exclusive_maximum' in value) ||
      (value.exclusive_maximum === true && isFiniteNumber(value.maximum))) &&
    (!('description' in value) || typeof value.description === 'string') &&
    (!('display_name' in value) || typeof value.display_name === 'string') &&
    (!('choices' in value) ||
      (value.type !== 'bool' &&
        Array.isArray(value.choices) &&
        value.choices.every((choice: unknown) =>
          matchesParameterType(choice, value.type as string, false),
        )))
  );
}

export function isStrategyCatalog(
  value: unknown,
): value is StrategyCatalogEntry[] {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        isRecord(entry) &&
        isNonEmptyString(entry.strategy_id) &&
        Number.isInteger(entry.strategy_version) &&
        (entry.strategy_version as number) > 0 &&
        isNonEmptyString(entry.display_name) &&
        Array.isArray(entry.parameters) &&
        entry.parameters.every(isStrategyParameterSchema),
    )
  );
}

const BACKTEST_ENGINE_SET: ReadonlySet<string> = new Set([
  'vectorized',
  'event_driven',
]);

const BACKTEST_DATA_GRANULARITY_SET: ReadonlySet<string> = new Set([
  'bar',
  'tick',
]);

export const BACKTEST_ALLOWED_DIRECTIONS_SET: ReadonlySet<string> = new Set([
  'long_only',
  'short_only',
  'long_and_short',
]);

const BACKTEST_PRICE_SOURCE_SET: ReadonlySet<string> = new Set([
  'open',
  'close',
]);

const BACKTEST_GAP_POLICY_SET: ReadonlySet<string> = new Set([
  'expire',
  'skip',
  'error',
]);

const BACKTEST_INTRABAR_EXIT_POLICY_SET: ReadonlySet<string> = new Set([
  'conservative',
  'stop_first',
  'take_profit_first',
  'error',
]);

function isBacktestStrategyPayload(
  value: unknown,
): value is BacktestStrategyPayload {
  return (
    isRecord(value) &&
    isNonEmptyString(value.strategy_id) &&
    (!('strategy_version' in value) ||
      value.strategy_version === null ||
      (Number.isInteger(value.strategy_version) &&
        (value.strategy_version as number) > 0)) &&
    isRecord(value.parameters) &&
    Object.values(value.parameters).every(isJsonValue)
  );
}

function isBacktestExecutionPayload(
  value: unknown,
): value is BacktestExecutionPayload {
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

export function isBacktestRequestPayload(
  value: unknown,
): value is BacktestRequestPayload {
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

export type BacktestCreationRequest = BacktestRequestPayload & {
  name?: string | null;
};
