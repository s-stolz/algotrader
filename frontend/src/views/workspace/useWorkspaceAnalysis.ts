import { computed, ref, type Ref } from 'vue';
import {
  getBacktestRun,
  fetchBacktestEquityCurve,
} from '@/api/backtesterClient';
import type {
  BacktestRun,
  EquityReplayResponse,
  EquityReplayPoint,
} from '@/types/backtesterContracts';
import { useRunResults } from './results/useRunResults';
import { errorMessage } from './workspaceErrors';
export function useWorkspaceAnalysis(backtestMembers: Ref<BacktestRun[]>) {
  type AnalysisState = {
    loading: boolean;
    preview: EquityReplayPoint[];
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
  const tradeResults = useRunResults(currentRows);
  const controllers = new Map<string, AbortController>();
  let active = true;
  let inflight = 0;

  function cancel(id: string) {
    controllers.get(id)?.abort();
    controllers.delete(id);
  }

  function pump(): void {
    if (!active) return;
    while (inflight < 2) {
      const id = selectedComparisonIds.value.find(
        (id) => analysis.value[id]?.loading && !controllers.has(id),
      );
      if (!id) return;
      const controller = new AbortController();
      controllers.set(id, controller);
      inflight++;
      const isCurrent = () => active && controllers.get(id) === controller;
      void (async () => {
        try {
          const detail = await getBacktestRun(id, false);
          if (!isCurrent()) return;
          if (detail.status !== 'succeeded')
            throw new Error('Run is no longer successful');
          analysis.value[id].detail = detail;
          const curve = await fetchBacktestEquityCurve(id, 2000, {
            signal: controller.signal,
            onPreview: (points) => {
              if (isCurrent()) analysis.value[id].preview = points;
            },
          });
          if (isCurrent())
            analysis.value[id] = {
              loading: false,
              error: null,
              preview: [],
              curve,
              detail,
            };
        } catch (error) {
          if (isCurrent())
            analysis.value[id] = {
              loading: false,
              error: errorMessage(error),
              preview: [],
              curve: null,
              detail: analysis.value[id]?.detail ?? null,
            };
        } finally {
          if (controllers.get(id) === controller) controllers.delete(id);
          inflight--;
          pump();
        }
      })();
    }
  }

  function loadAnalysis(refresh = false): void {
    active = true;
    tradeResults.start();
    const ids = selectedComparisonIds.value;
    for (const id of controllers.keys()) {
      if (!ids.includes(id)) cancel(id);
    }
    analysis.value = Object.fromEntries(
      ids.flatMap((id) =>
        analysis.value[id] ? [[id, analysis.value[id]]] : [],
      ),
    );
    for (const id of ids) {
      const previous = analysis.value[id];
      // Failed reads retry only on explicit action, never on background refresh.
      if (
        previous &&
        (!refresh ||
          previous.error ||
          previous.curve?.availability === 'unavailable')
      )
        continue;
      cancel(id);
      analysis.value[id] = {
        loading: true,
        error: null,
        preview: [],
        curve: previous?.curve ?? null,
        detail: previous?.detail ?? null,
      };
    }
    pump();
  }

  function retryAnalysis(id: string) {
    if (!selectedComparisonIds.value.includes(id)) return;
    cancel(id);
    analysis.value[id] = {
      loading: true,
      error: null,
      preview: [],
      curve: null,
      detail: analysis.value[id]?.detail ?? null,
    };
    pump();
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
    tradeResults.stop();
    active = false;
    for (const id of controllers.keys()) cancel(id);
    for (const state of Object.values(analysis.value)) {
      state.preview = [];
    }
  }
  return {
    analysis,
    tradeResults,
    selectedComparisonIds,
    currentRows,
    loadAnalysis,
    retryAnalysis,
    setComparison,
    toggleComparison,
    stop,
  };
}
