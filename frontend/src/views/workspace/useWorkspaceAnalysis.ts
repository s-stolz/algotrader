import { computed, ref, type Ref } from 'vue';
import {
  getBacktestRun,
  fetchBacktestEquityCurve,
} from '@/api/backtesterClient';
import type {
  BacktestRun,
  EquityReplayResponse,
} from '@/types/backtesterContracts';
import { errorMessage } from './workspaceErrors';
export function useWorkspaceAnalysis(backtestMembers: Ref<BacktestRun[]>) {
  type AnalysisState = {
    loading: boolean;
    error: string | null;
    curve: EquityReplayResponse | null;
    detail: BacktestRun | null;
  };
  const analysis = ref<Record<string, AnalysisState>>({});
  const selectedComparisonIds = ref<string[]>([]);
  const currentRows = computed(() =>
    backtestMembers.value.map(
      (run) => analysis.value[run.run_id]?.detail ?? run,
    ),
  );
  let analysisSequence = 0;
  const analysisTokens = new Map<string, number>();
  function loadAnalysis(refresh = false): void {
    const ids = [...selectedComparisonIds.value];
    const kept = new Set(ids);
    for (const id of analysisTokens.keys()) {
      if (!kept.has(id)) analysisTokens.delete(id);
    }
    analysis.value = Object.fromEntries(
      ids.flatMap((id) =>
        analysis.value[id] ? [[id, analysis.value[id]]] : [],
      ),
    );
    for (const id of ids) {
      if (
        !refresh &&
        analysis.value[id] &&
        (!analysis.value[id].loading || analysisTokens.has(id))
      )
        continue;
      const token = ++analysisSequence;
      analysisTokens.set(id, token);
      analysis.value[id] = {
        loading: true,
        error: null,
        curve: analysis.value[id]?.curve ?? null,
        detail: analysis.value[id]?.detail ?? null,
      };
      void (async () => {
        try {
          const detail = await getBacktestRun(id);
          if (detail.status !== 'succeeded')
            throw new Error('Run is no longer successful');
          if (analysisTokens.get(id) === token)
            analysis.value[id] = {
              loading: true,
              error: null,
              curve: analysis.value[id]?.curve ?? null,
              detail,
            };
          const curve = await fetchBacktestEquityCurve(id);
          if (analysisTokens.get(id) === token)
            analysis.value[id] = {
              loading: false,
              error: null,
              curve,
              detail,
            };
        } catch (error) {
          if (analysisTokens.get(id) === token)
            analysis.value[id] = {
              loading: false,
              error: errorMessage(error),
              curve: analysis.value[id]?.curve ?? null,
              detail: analysis.value[id]?.detail ?? null,
            };
        }
      })();
    }
  }

  function setComparison(ids: string[], refresh = false): void {
    const nextIds = [...new Set(ids)].filter((id) =>
      currentRows.value.some(
        (run) => run.run_id === id && run.status === 'succeeded',
      ),
    );
    if (
      !refresh &&
      nextIds.length === selectedComparisonIds.value.length &&
      nextIds.every((id, index) => id === selectedComparisonIds.value[index])
    )
      return;
    selectedComparisonIds.value = nextIds;
    loadAnalysis(refresh);
  }

  function toggleComparison(run: BacktestRun): void {
    if (run.status !== 'succeeded') return;
    setComparison(
      selectedComparisonIds.value.includes(run.run_id)
        ? selectedComparisonIds.value.filter((id) => id !== run.run_id)
        : [...selectedComparisonIds.value, run.run_id],
    );
  }

  function stop() {
    analysisTokens.clear();
  }
  return {
    analysis,
    selectedComparisonIds,
    currentRows,
    loadAnalysis,
    setComparison,
    toggleComparison,
    stop,
  };
}
