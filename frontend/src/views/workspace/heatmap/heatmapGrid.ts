import {
  tupleKey,
  type HeatmapSnapshot,
} from '@/types/backtest/heatmapSnapshot';
import {
  formatMetric,
  heatmapMetrics,
  metricValue,
  type HeatmapMetric,
} from './heatmapMetrics';
import type { BacktestRun } from '@/types/backtesterContracts';
export type HeatmapCell = {
  x: number;
  y: number;
  run?: BacktestRun;
  value: number | null;
  state: 'ready' | 'excluded' | 'unavailable';
  description: string;
};
export function heatmapGrid(
  snapshot: HeatmapSnapshot,
  x: string,
  y: string,
  fixed: Record<string, string>,
  metric: HeatmapMetric,
): HeatmapCell[] {
  const xd = snapshot.dimensions.find((field) => field.key === x);
  const yd = snapshot.dimensions.find((field) => field.key === y);
  if (!xd?.numeric || !yd?.numeric || xd === yd) return [];
  return yd.options.flatMap((yv, yi) =>
    xd.options.map((xv, xi) => {
      const inputs = { ...fixed, [x]: xv.value, [y]: yv.value };
      const member = snapshot.byTuple.get(
        tupleKey(snapshot.dimensions, inputs),
      );
      const run = member?.run;
      const value = run ? metricValue(run, metric) : null;
      const state = !run
        ? 'excluded'
        : value === null
          ? 'unavailable'
          : 'ready';
      const reason = !run
        ? 'No Run for this combination'
        : run.status !== 'succeeded'
          ? `${run.status}: ${run.error_message ?? run.cancellation_reason ?? 'Result unavailable'}`
          : value === null
            ? 'Saved metric unavailable'
            : `${heatmapMetrics.find((entry) => entry.value === metric)!.label}: ` +
              formatMetric(value, metric);
      return {
        x: xi,
        y: yi,
        run,
        value,
        state,
        description: [
          run ? `Run #${run.run_ordinal + 1} · ${run.run_id}` : 'No Run',
          ...snapshot.dimensions.map(
            (field) =>
              `${field.label}: ${
                field.options.find(
                  (option) => option.value === inputs[field.key],
                )?.label ?? '—'
              }`,
          ),
          reason,
        ].join('\n'),
      };
    }),
  );
}
