import {
  isRecord,
  isFiniteNumber,
  isNonEmptyString,
  isNullableNumber,
} from '../transportValues';
import type { BacktestExitReason, BacktestTradeDirection } from './requests';

export const BACKTEST_RESULT_SCHEMA_VERSION = 3 as const;

export interface EquityReplayPoint {
  timestamp_ms: number;
  equity: number;
  drawdown_pct: number;
}

export interface EquityReplayResponse {
  availability: 'exact' | 'unavailable';
  reason:
    | 'replay_metadata_missing'
    | 'fingerprint_mismatch'
    | 'unsupported_replay_shape'
    | null;
  source_point_count: number;
  returned_point_count: number;
  sampled: boolean;
  equity_curve: EquityReplayPoint[];
}

export function isEquityReplayResponse(
  value: unknown,
): value is EquityReplayResponse {
  if (!isRecord(value) || !Array.isArray(value.equity_curve)) return false;
  if (
    typeof value.source_point_count !== 'number' ||
    !Number.isInteger(value.source_point_count) ||
    typeof value.returned_point_count !== 'number' ||
    !Number.isInteger(value.returned_point_count) ||
    typeof value.sampled !== 'boolean' ||
    value.equity_curve.length !== value.returned_point_count
  )
    return false;
  let previousTimestamp = -Infinity;
  for (const point of value.equity_curve) {
    if (
      !isRecord(point) ||
      typeof point.timestamp_ms !== 'number' ||
      !Number.isInteger(point.timestamp_ms) ||
      point.timestamp_ms <= previousTimestamp ||
      !isFiniteNumber(point.equity) ||
      !isFiniteNumber(point.drawdown_pct) ||
      point.drawdown_pct > 0
    )
      return false;
    previousTimestamp = point.timestamp_ms;
  }
  if (value.availability === 'exact') {
    return (
      value.reason === null &&
      value.source_point_count > 0 &&
      value.returned_point_count > 0 &&
      value.returned_point_count <= value.source_point_count &&
      value.sampled === value.returned_point_count < value.source_point_count
    );
  }
  return (
    value.availability === 'unavailable' &&
    [
      'replay_metadata_missing',
      'fingerprint_mismatch',
      'unsupported_replay_shape',
    ].includes(String(value.reason)) &&
    value.source_point_count === 0 &&
    value.returned_point_count === 0 &&
    value.sampled === false
  );
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

const BACKTEST_EXIT_REASON_SET: ReadonlySet<string> = new Set([
  'signal',
  'stop_loss',
  'take_profit',
]);

const BACKTEST_TRADE_DIRECTION_SET: ReadonlySet<string> = new Set([
  'long',
  'short',
]);

export function isBacktestClosedTrade(
  value: unknown,
): value is BacktestClosedTrade {
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

export function isBacktestClosedTradeArray(
  value: unknown,
): value is BacktestClosedTrade[] {
  return (
    Array.isArray(value) &&
    value.every(isBacktestClosedTrade) &&
    value.every(
      (trade, index) =>
        index === 0 || trade.sequence > value[index - 1].sequence,
    )
  );
}

export function isBacktestFill(value: unknown): value is BacktestFill {
  if (!isRecord(value)) return false;
  return (
    Number.isInteger(value.sequence) &&
    (value.sequence as number) >= 0 &&
    isFiniteNumber(value.timestamp_ms) &&
    value.timestamp_ms > 0 &&
    isNonEmptyString(value.symbol) &&
    (value.side === 'buy' || value.side === 'sell') &&
    isFiniteNumber(value.quantity) &&
    value.quantity > 0 &&
    isFiniteNumber(value.price) &&
    isFiniteNumber(value.fees) &&
    (value.exit_reason === null ||
      (typeof value.exit_reason === 'string' &&
        BACKTEST_EXIT_REASON_SET.has(value.exit_reason)))
  );
}

export function isBacktestFillArray(value: unknown): value is BacktestFill[] {
  return (
    Array.isArray(value) &&
    value.every(isBacktestFill) &&
    value.every(
      (fill, index) => index === 0 || fill.sequence > value[index - 1].sequence,
    )
  );
}
