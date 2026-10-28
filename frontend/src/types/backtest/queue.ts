import { isRecord, isNonEmptyString } from '../transportValues';
import { type BacktestBatch, isBatchOutcomeCounts } from './batches';
import { isEpochMs, isOrdinal } from './validation';

export type BacktestWorkerAvailability =
  | 'healthy'
  | 'stale'
  | 'unavailable'
  | 'faulted';

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
  active_run: {
    run_id: string;
    started_at_ms: number;
    batch_id: string | null;
    member_ordinal: number | null;
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
      (value.active_run.batch_id !== null &&
        !isNonEmptyString(value.active_run.batch_id)) ||
      (value.active_run.member_ordinal !== null &&
        !isOrdinal(value.active_run.member_ordinal)) ||
      (value.active_run.batch_id === null) !==
        (value.active_run.member_ordinal === null))
  )
    return false;
  const identities = new Set<string>();
  if (isRecord(value.active_run))
    identities.add(
      value.active_run.batch_id === null
        ? `run:${value.active_run.run_id}`
        : `batch:${value.active_run.batch_id}`,
    );
  return value.queued.every((entry: unknown, index: number) => {
    if (
      !isRecord(entry) ||
      !isEpochMs(entry.submitted_at_ms) ||
      entry.estimated_position !== index + 1
    )
      return false;
    const isStandalone =
      entry.entry_type === 'standalone' &&
      isNonEmptyString(entry.run_id) &&
      entry.batch_id === null &&
      entry.next_member_ordinal === null &&
      entry.outcome_counts === null;
    const isBatch =
      entry.entry_type === 'batch' &&
      entry.run_id === null &&
      isNonEmptyString(entry.batch_id) &&
      isOrdinal(entry.next_member_ordinal) &&
      isBatchOutcomeCounts(entry.outcome_counts);
    if (!isStandalone && !isBatch) return false;
    const identity = isStandalone
      ? `run:${entry.run_id}`
      : `batch:${entry.batch_id}`;
    if (identities.has(identity)) return false;
    identities.add(identity);
    return true;
  });
}
