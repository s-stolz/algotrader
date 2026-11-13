import type {
  Backtest,
  BacktestQueueSnapshot,
} from '@/types/backtesterContracts';
import { backtestName } from '@/views/backtestWorkspaceRuns';

export function activityRows(
  snapshot: BacktestQueueSnapshot | null,
  backtests: Backtest[],
) {
  if (!snapshot) return [];
  const entries = [
    ...(snapshot.active_run
      ? [
          {
            id: snapshot.active_run.backtest_id,
            ordinal: snapshot.active_run.run_ordinal,
            status: 'Running' as const,
            counts: null,
          },
        ]
      : []),
    ...snapshot.queued.map((entry) => ({
      id: entry.backtest_id,
      ordinal: entry.next_run_ordinal,
      status: 'Queued' as const,
      counts: entry.outcome_counts,
    })),
  ];
  return entries.map((entry) => {
    const backtest = backtests.find((item) => item.backtest_id === entry.id);
    const counts = entry.counts;
    return {
      ...entry,
      name: backtest ? backtestName(backtest) : 'Backtest',
      finished: counts
        ? counts.succeeded + counts.failed + counts.cancelled
        : (backtest?.settled_count ?? 0),
      total: counts
        ? Object.values(counts).reduce((sum, count) => sum + count, 0)
        : (backtest?.total_count ?? 0),
    };
  });
}
