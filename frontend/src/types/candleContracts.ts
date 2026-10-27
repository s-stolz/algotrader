import { isRecord, isFiniteNumber, isNonEmptyString } from './transportValues';

export interface Candle {
  timestamp_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartCandle extends Candle {
  time: number;
}

export interface CandleFetchOptions {
  startMs?: number | null;
  endMs?: number | null;
  limit?: number | null;
  exchange?: string | null;
}

export interface CandleBatchPayload {
  symbol: string;
  exchange?: string | null;
  candles: Candle[];
}

export interface CandleBatchResponse {
  status: string;
  added_candles: number;
  total_candles: number;
}

export function isCandle(value: unknown): value is Candle {
  if (!isRecord(value)) {
    return false;
  }

  if (
    !isFiniteNumber(value.timestamp_ms) ||
    value.timestamp_ms <= 0 ||
    !isFiniteNumber(value.open) ||
    !isFiniteNumber(value.high) ||
    !isFiniteNumber(value.low) ||
    !isFiniteNumber(value.close) ||
    !isFiniteNumber(value.volume)
  ) {
    return false;
  }

  return (
    value.high >= Math.max(value.low, value.open, value.close) &&
    value.low <= Math.min(value.open, value.close)
  );
}

export function isCandleArray(value: unknown): value is Candle[] {
  return Array.isArray(value) && value.every(isCandle);
}

export function isChartCandle(value: unknown): value is ChartCandle {
  return isCandle(value) && isRecord(value) && isFiniteNumber(value.time);
}

export function toChartCandle(candle: Candle): ChartCandle {
  return {
    ...candle,
    time: Math.floor(candle.timestamp_ms / 1000),
  };
}

export function isCandleBatchResponse(
  value: unknown,
): value is CandleBatchResponse {
  return (
    isRecord(value) &&
    isNonEmptyString(value.status) &&
    isFiniteNumber(value.added_candles) &&
    isFiniteNumber(value.total_candles)
  );
}
