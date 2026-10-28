import { computed, ref, watch, type Ref } from 'vue';
import {
  getBacktestRun,
  fetchBacktestEquityCurve,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type {
  BacktestRun,
  EquityReplayResponse,
} from '@/types/backtesterContracts';
import { errorMessage } from './workspaceErrors';
export function useWorkspaceAnalysis(selection: {
  selectedBatchId: Ref<string | null>;
  batchMembers: Ref<BacktestRun[]>;
  selectedRun: Ref<BacktestRun | null>;
}) {
  const { selectedBatchId, batchMembers, selectedRun } = selection;
  const workspaceStore = useBacktestWorkspaceStore();
  type AnalysisState = {
    loading: boolean;
    error: string | null;
    curve: EquityReplayResponse | null;
    detail: BacktestRun | null;
  };
  const analysis = ref<Record<string, AnalysisState>>({});
  const selectedComparisonIds = ref<string[]>([]);
  const currentRows = computed(() =>
    (selectedBatchId.value
      ? batchMembers.value
      : selectedRun.value
        ? [selectedRun.value]
        : []
    ).map((run) => analysis.value[run.run_id]?.detail ?? run),
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
      const nameReadRevision = workspaceStore.nameRevision;
      analysisTokens.set(id, token);
      analysis.value[id] = {
        loading: true,
        error: null,
        curve: analysis.value[id]?.curve ?? null,
        detail: analysis.value[id]?.detail ?? null,
      };
      void (async () => {
        try {
          const detail = workspaceStore.preserveRunName(
            await getBacktestRun(id),
            nameReadRevision,
          );
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
              detail: workspaceStore.preserveRunName(detail, nameReadRevision),
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

  watch(
    () => workspaceStore.nameRevision,
    () => {
      for (const state of Object.values(analysis.value)) {
        if (state.detail)
          state.detail = workspaceStore.preserveRunName(state.detail, -1);
      }
    },
  );
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
