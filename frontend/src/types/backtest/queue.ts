import { isRecord, isNonEmptyString } from '../transportValues';
import { type Backtest, isBacktestOutcomeCounts } from './backtests';
import { isEpochMs, isOrdinal } from './validation';

export type BacktestWorkerAvailability =
  'healthy' | 'stale' | 'unavailable' | 'faulted';

export interface BacktestQueueEntry {
  backtest_id: string;
  submitted_at_ms: number;
  estimated_position: number;
  next_run_ordinal: number;
  outcome_counts: Backtest['outcome_counts'];
}

export interface BacktestQueueSnapshot {
  snapshot_at_ms: number;
  active_run: {
    run_id: string;
    started_at_ms: number;
    backtest_id: string;
    run_ordinal: number;
  } | null;
  last_heartbeat_ms: number | null;
  availability: BacktestWorkerAvailability;
  stale_after_ms: number;
  operational_faults: { code: string; message: string }[];
  queued: BacktestQueueEntry[];
}

export function isBacktestQueueSnapshot(
  value: unknown,
): value is BacktestQueueSnapshot {
  if (
    !isRecord(value) ||
    !isEpochMs(value.snapshot_at_ms) ||
    !isEpochMs(value.stale_after_ms) ||
    value.stale_after_ms === 0 ||
    (value.last_heartbeat_ms !== null && !isEpochMs(value.last_heartbeat_ms)) ||
    !['healthy', 'stale', 'unavailable', 'faulted'].includes(
      String(value.availability),
    ) ||
    !Array.isArray(value.operational_faults) ||
    !value.operational_faults.every(
      (fault: unknown) =>
        isRecord(fault) &&
        isNonEmptyString(fault.code) &&
        isNonEmptyString(fault.message),
    ) ||
    !Array.isArray(value.queued)
  )
    return false;
  if (
    value.active_run !== null &&
    (!isRecord(value.active_run) ||
      !isNonEmptyString(value.active_run.run_id) ||
      !isEpochMs(value.active_run.started_at_ms) ||
      !isNonEmptyString(value.active_run.backtest_id) ||
      !isOrdinal(value.active_run.run_ordinal))
  )
    return false;
  const identities = new Set<string>();
  if (isRecord(value.active_run))
    identities.add(value.active_run.backtest_id as string);
  return value.queued.every((entry: unknown, index: number) => {
    if (
      !isRecord(entry) ||
      !isEpochMs(entry.submitted_at_ms) ||
      entry.estimated_position !== index + 1
    )
      return false;
    if (
      !isNonEmptyString(entry.backtest_id) ||
      !isOrdinal(entry.next_run_ordinal) ||
      !isBacktestOutcomeCounts(entry.outcome_counts)
    )
      return false;
    const identity = entry.backtest_id;
    if (identities.has(identity)) return false;
    identities.add(identity);
    return true;
  });
}
