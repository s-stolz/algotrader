import { isRecord, isFiniteNumber, isNullableString } from './transportValues';

export const BACKTEST_PROGRESS_STAGES = [
  'loading_data',
  'preparing_indicators',
  'simulating',
  'calculating_results',
  'saving',
] as const;
export type BacktestProgressStage = (typeof BACKTEST_PROGRESS_STAGES)[number];
export interface BacktestProgressMessage {
  type: 'backtestProgress';
  run_id: string;
  stage: BacktestProgressStage;
  processed_candles?: number;
  total_candles?: number;
}

export interface BacktestChangedMessage {
  type: 'backtestChanged';
}
export interface BacktestConnectionMessage {
  type: 'backtestConnection';
  connected: boolean;
}
export interface BacktestHealthMessage {
  type: 'backtestHealth';
  run_id: string | null;
  heartbeat_at_ms: number;
  fault_code: string | null;
  fault_message: string | null;
}
export type BacktestEventMessage =
  | BacktestChangedMessage
  | BacktestConnectionMessage
  | BacktestHealthMessage
  | BacktestProgressMessage;

export function isBacktestEventMessage(
  value: unknown,
): value is BacktestEventMessage {
  if (!isRecord(value)) return false;
  if (value.type === 'backtestProgress')
    return (
      typeof value.run_id === 'string' &&
      value.run_id.length > 0 &&
      BACKTEST_PROGRESS_STAGES.some((stage) => stage === value.stage) &&
      ((value.processed_candles === undefined &&
        value.total_candles === undefined) ||
        (value.stage === 'simulating' &&
          typeof value.processed_candles === 'number' &&
          Number.isSafeInteger(value.processed_candles) &&
          typeof value.total_candles === 'number' &&
          Number.isSafeInteger(value.total_candles) &&
          value.processed_candles >= 0 &&
          value.total_candles > 0 &&
          value.processed_candles <= value.total_candles))
    );
  if (value.type === 'backtestChanged') return true;
  if (value.type === 'backtestConnection')
    return typeof value.connected === 'boolean';
  return (
    value.type === 'backtestHealth' &&
    isNullableString(value.run_id) &&
    isFiniteNumber(value.heartbeat_at_ms) &&
    value.heartbeat_at_ms > 0 &&
    isNullableString(value.fault_code) &&
    isNullableString(value.fault_message)
  );
}
