import { isRecord, isFiniteNumber, isNullableString } from './transportValues';

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
  | BacktestHealthMessage;

export function isBacktestEventMessage(
  value: unknown,
): value is BacktestEventMessage {
  if (!isRecord(value)) return false;
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
