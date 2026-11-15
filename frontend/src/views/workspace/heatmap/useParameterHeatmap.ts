import { computed, ref, watch, type Ref } from 'vue';
import type { Backtest, BacktestRun } from '@/types/backtesterContracts';
import { adaptHeatmapSnapshot } from '@/types/backtest/heatmapSnapshot';
import { metricBounds, type HeatmapMetric } from './heatmapMetrics';
import { heatmapGrid } from './heatmapGrid';
export function useParameterHeatmap(
  saved: Ref<{ backtest: Backtest; runs: BacktestRun[] }>,
) {
  const x = ref<string | null>(null);
  const y = ref<string | null>(null);
  const metric = ref<HeatmapMetric | null>(null);
  const fixed = ref<Record<string, string>>({});
  const adapted = computed(() => {
    try {
      return {
        snapshot: adaptHeatmapSnapshot(saved.value.backtest, saved.value.runs),
        error: null,
      };
    } catch (error) {
      return {
        snapshot: null,
        error: error instanceof Error ? error.message : 'Invalid saved data.',
      };
    }
  });
  watch(
    () => saved.value.backtest.backtest_id,
    () => {
      x.value = y.value = null;
      metric.value = null;
      fixed.value = {};
    },
    { flush: 'sync' },
  );
  watch(
    adapted,
    ({ snapshot }) => {
      if (snapshot && !Object.keys(fixed.value).length)
        fixed.value = { ...snapshot.members[0].inputs };
    },
    { immediate: true, flush: 'sync' },
  );
  const axes = computed(
    () =>
      adapted.value.snapshot?.dimensions.filter(
        (field) => field.numeric && field.options.length > 1,
      ) ?? [],
  );
  const fixedDimensions = computed(
    () =>
      adapted.value.snapshot?.dimensions.filter(
        (field) =>
          field.options.length > 1 &&
          field.key !== x.value &&
          field.key !== y.value,
      ) ?? [],
  );
  const xDimension = computed(() =>
    axes.value.find((field) => field.key === x.value),
  );
  const yDimension = computed(() =>
    axes.value.find((field) => field.key === y.value),
  );
  const ready = computed(
    () =>
      !!(
        xDimension.value &&
        yDimension.value &&
        x.value !== y.value &&
        metric.value
      ),
  );
  const cells = computed(() =>
    ready.value && adapted.value.snapshot
      ? heatmapGrid(
          adapted.value.snapshot,
          x.value!,
          y.value!,
          fixed.value,
          metric.value!,
        )
      : [],
  );
  const bounds = computed(() =>
    metric.value ? metricBounds(saved.value.runs, metric.value) : null,
  );
  const emptyReason = computed(() =>
    !cells.value.some((cell) => cell.run)
      ? 'No Runs in this slice'
      : !cells.value.some((cell) => cell.run?.status === 'succeeded')
        ? 'No successful Runs in this slice'
        : !cells.value.some((cell) => cell.value !== null)
          ? 'No usable values for this metric in this slice'
          : null,
  );
  function swap() {
    [x.value, y.value] = [y.value, x.value];
  }
  return {
    x,
    y,
    metric,
    fixed,
    axes,
    fixedDimensions,
    xDimension,
    yDimension,
    ready,
    cells,
    bounds,
    emptyReason,
    adapted,
    swap,
  };
}
