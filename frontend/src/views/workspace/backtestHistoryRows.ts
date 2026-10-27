import type { BacktestBatch, BacktestRun } from '@/types/backtesterContracts';
import {
  batchName,
  runName,
  runMarket,
  strategyVersion,
  timeframeDuration,
  type HistorySortKey,
} from '../backtestWorkspaceRuns';
export type HistoryEntry =
  | { kind: 'run'; run: BacktestRun }
  | { kind: 'batch'; batch: BacktestBatch };
export function batchMarkets(batch: BacktestBatch): string[] {
  return batch.market_contexts.map((market) =>
    market.exchange ? `${market.exchange}:${market.symbol}` : market.symbol,
  );
}
export function batchTimeframes(batch: BacktestBatch): string[] {
  return batch.timeframes;
}
export function rowKey(entry: HistoryEntry): string {
  return entry.kind === 'run' ? entry.run.run_id : entry.batch.batch_id;
}

function entrySortValue(
  entry: HistoryEntry,
  key: HistorySortKey | 'progress',
): string | number {
  if (entry.kind === 'run') {
    const run = entry.run;
    const values: Record<HistorySortKey | 'progress', string | number> = {
      name: runName(run),
      type: 'Standalone',
      strategy: `${run.request.strategy.strategy_id} ${strategyVersion(run)}`,
      market: runMarket(run),
      timeframe:
        timeframeDuration(run.request.timeframe) ?? run.request.timeframe,
      start: run.request.start_ms,
      end: run.request.end_ms,
      status: run.status,
      duration: run.request.end_ms - run.request.start_ms,
      submitted: run.submitted_at_ms,
      progress: ['succeeded', 'failed', 'cancelled'].includes(run.status)
        ? 1
        : 0,
    };
    return values[key];
  }
  const batch = entry.batch;
  const shared = batch.accepted_definition.shared_request;
  const durations = batchTimeframes(batch)
    .map(timeframeDuration)
    .filter((value) => value !== null);
  const values: Record<HistorySortKey | 'progress', string | number> = {
    name: batchName(batch),
    type: 'Parameter Sweep',
    strategy: `${batch.strategy_id} v${batch.strategy_version}`,
    market: batchMarkets(batch).join(', '),
    timeframe: durations.length
      ? Math.min(...durations)
      : batchTimeframes(batch).join(', '),
    start: Number(shared.start_ms ?? 0),
    end: Number(shared.end_ms ?? 0),
    status: batch.status,
    duration: Number(shared.end_ms ?? 0) - Number(shared.start_ms ?? 0),
    submitted: batch.accepted_at_ms,
    progress: batch.total_count ? batch.settled_count / batch.total_count : 0,
  };
  return values[key];
}
export function compareHistoryEntries(
  left: HistoryEntry,
  right: HistoryEntry,
  key: HistorySortKey | 'progress',
): number {
  const a = entrySortValue(left, key);
  const b = entrySortValue(right, key);
  const result =
    typeof a === 'number' && typeof b === 'number'
      ? a - b
      : String(a).localeCompare(String(b), undefined, { numeric: true });
  return (
    result ||
    String(entrySortValue(left, 'name')).localeCompare(
      String(entrySortValue(right, 'name')),
      undefined,
      { numeric: true },
    ) ||
    rowKey(left).localeCompare(rowKey(right), undefined, { numeric: true })
  );
}
