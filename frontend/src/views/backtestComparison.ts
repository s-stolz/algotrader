import type { BacktestRun, EquityReplayPoint } from '@/types/backtesterContracts';
import { runMarket, runName, savedMetric, strategyVersion, timeframeDuration } from './backtestWorkspaceRuns';

export type ComparisonSortKey = 'name' | 'status' | 'market' | 'timeframe' | 'return' |
  'drawdown' | 'capital' | 'ordinal';
export type ReplaySeries = { runId: string; name: string; ordinal?: number;
  points: EquityReplayPoint[] };

export function compareRuns(left: BacktestRun, right: BacktestRun,
  key: ComparisonSortKey): number {
  const value = (run: BacktestRun): string | number | null => {
    switch (key) {
      case 'name': return runName(run);
      case 'status': return run.status;
      case 'market': return runMarket(run);
      case 'timeframe': return timeframeDuration(run.request.timeframe) ?? run.request.timeframe;
      case 'return': return savedMetric(run, 'total_return_pct');
      case 'drawdown': {
        const drawdown = savedMetric(run, 'max_drawdown_pct');
        return drawdown === null ? null : Math.abs(drawdown);
      }
      case 'capital': return run.request.initial_capital;
      case 'ordinal': return run.member_ordinal ?? 0;
    }
  };
  const a = value(left);
  const b = value(right);
  const order = a == null ? (b == null ? 0 : 1) : b == null ? -1 :
    typeof a === 'number' && typeof b === 'number' ? a - b :
      String(a).localeCompare(String(b), undefined, { numeric: true });
  return order || (left.member_ordinal ?? 0) - (right.member_ordinal ?? 0) ||
    left.run_id.localeCompare(right.run_id);
}

export function differingSettings(runs: BacktestRun[]): string[] {
  if (runs.length < 2) return [];
  const settings: [string, (run: BacktestRun) => unknown][] = [
    ['Market', (run) => runMarket(run)],
    ['Timeframe', (run) => run.request.timeframe],
    ['dates', (run) => [run.request.start_ms, run.request.end_ms]],
    ['strategy/version', (run) => [run.request.strategy.strategy_id, strategyVersion(run)]],
    ['Initial capital', (run) => run.request.initial_capital],
    ['engine', (run) => run.request.engine],
    ['costs', (run) => [run.request.execution.commission_bps,
      run.request.execution.slippage_bps]],
    ['Allowed Directions', (run) => run.request.execution.allowed_directions],
  ];
  return settings.filter(([, value]) => {
    const first = JSON.stringify(value(runs[0]!));
    return runs.some((run) => JSON.stringify(value(run)) !== first);
  }).map(([name]) => name);
}
