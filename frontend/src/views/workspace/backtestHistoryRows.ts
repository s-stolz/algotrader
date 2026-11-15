import type { Backtest } from '@/types/backtesterContracts';
import {
  backtestName,
  timeframeDuration,
  type HistorySortKey,
} from '../backtestWorkspaceRuns';
export type HistoryEntry = { backtest: Backtest };
export function backtestMarkets(backtest: Backtest): string[] {
  return backtest.market_contexts.map((market) =>
    market.exchange ? `${market.exchange}:${market.symbol}` : market.symbol,
  );
}
export function backtestTimeframes(backtest: Backtest): string[] {
  return backtest.timeframes;
}
export function rowKey(entry: HistoryEntry): string {
  return entry.backtest.backtest_id;
}

function entrySortValue(
  entry: HistoryEntry,
  key: HistorySortKey | 'progress',
): string | number {
  const backtest = entry.backtest;
  const shared = backtest.accepted_definition.shared_request;
  const durations = backtestTimeframes(backtest)
    .map(timeframeDuration)
    .filter((value) => value !== null);
  const values: Record<HistorySortKey | 'progress', string | number> = {
    name: backtestName(backtest),
    strategy: `${backtest.strategy_id} v${backtest.strategy_version}`,
    market: backtestMarkets(backtest).join(', '),
    timeframe: durations.length
      ? Math.min(...durations)
      : backtestTimeframes(backtest).join(', '),
    start: Number(shared.start_ms ?? 0),
    end: Number(shared.end_ms ?? 0),
    status: backtest.status,
    duration: Number(shared.end_ms ?? 0) - Number(shared.start_ms ?? 0),
    submitted: backtest.accepted_at_ms,
    progress: backtest.total_count
      ? backtest.settled_count / backtest.total_count
      : 0,
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
