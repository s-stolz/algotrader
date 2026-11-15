import type { BacktestRun } from '@/types/backtesterContracts';
import { decodeProfitFactor } from '@/types/backtest/results';
import { savedMetric } from '../../backtestWorkspaceRuns';

export const heatmapMetrics = [
  { value: 'return', label: 'Return %', unit: '%' },
  { value: 'factor', label: 'Profit factor', unit: '' },
  { value: 'drawdown', label: 'Max drawdown %', unit: '%' },
  { value: 'equity', label: 'Ending equity', unit: ' account units' },
] as const;
export type HeatmapMetric = (typeof heatmapMetrics)[number]['value'];
export function metricValue(
  run: BacktestRun,
  metric: HeatmapMetric,
): number | null {
  if (run.status !== 'succeeded') return null;
  if (metric === 'factor')
    return decodeProfitFactor(run.metrics?.profit_factor);
  const value = savedMetric(
    run,
    {
      return: 'total_return_pct',
      drawdown: 'max_drawdown_pct',
      equity: 'ending_equity',
    }[metric],
  );
  return value !== null && metric === 'drawdown' ? Math.abs(value) : value;
}
export function metricBounds(
  runs: BacktestRun[],
  metric: HeatmapMetric,
): [number, number] | null {
  const finite = runs
    .map((run) => metricValue(run, metric))
    .filter(
      (value): value is number => value !== null && Number.isFinite(value),
    );
  return finite.length ? [Math.min(...finite), Math.max(...finite)] : null;
}
export function metricScore(
  value: number,
  bounds: [number, number] | null,
  metric: HeatmapMetric,
): number {
  if (value === Infinity) return 1;
  if (!bounds || bounds[0] === bounds[1]) return 0.5;
  const score = (value - bounds[0]) / (bounds[1] - bounds[0]);
  return metric === 'drawdown' ? 1 - score : score;
}
export function formatMetric(
  value: number,
  metric: HeatmapMetric,
  rounded = false,
): string {
  const text =
    value === Infinity
      ? '∞'
      : rounded
        ? value.toLocaleString('en-US', { maximumFractionDigits: 2 })
        : String(value);
  return text + heatmapMetrics.find((entry) => entry.value === metric)!.unit;
}
