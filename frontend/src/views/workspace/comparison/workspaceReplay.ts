import { computed } from 'vue';
import type { BacktestRun } from '@/types/backtesterContracts';
import { differingSettings, type ReplaySeries } from '../../backtestComparison';
import { runName as comparisonRunLabel } from '../../backtestWorkspaceRuns';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
export function workspaceReplay(inspection: BacktestWorkspace['inspection']) {
  const { currentRows, selectedComparisonIds, analysis } = inspection;
  const selectedComparisonRuns = computed(() =>
    selectedComparisonIds.value
      .map((id) => currentRows.value.find((run) => run.run_id === id))
      .filter((run): run is BacktestRun => run?.status === 'succeeded'),
  );
  const compatibilityDifferences = computed(() =>
    differingSettings(selectedComparisonRuns.value),
  );
  const curveStatusIds = computed(() =>
    selectedComparisonIds.value.filter(
      (id) =>
        analysis.value[id]?.error ||
        analysis.value[id]?.curve?.availability === 'unavailable',
    ),
  );
  const hasSampledCurve = computed(() =>
    selectedComparisonIds.value.some(
      (id) => analysis.value[id]?.curve?.sampled,
    ),
  );
  const chartSeries = computed<ReplaySeries[]>(() =>
    selectedComparisonRuns.value.flatMap((run) => {
      const curve = analysis.value[run.run_id]?.curve;
      return curve?.availability === 'exact'
        ? [
            {
              runId: run.run_id,
              name: comparisonRunLabel(run),
              ordinal: run.member_ordinal,
              points: curve.equity_curve,
            },
          ]
        : [];
    }),
  );
  function analysisRunName(id: string): string {
    const run = currentRows.value.find((candidate) => candidate.run_id === id);
    return run ? comparisonRunLabel(run) : id;
  }

  return {
    compatibilityDifferences,
    curveStatusIds,
    hasSampledCurve,
    chartSeries,
    analysisRunName,
  };
}
