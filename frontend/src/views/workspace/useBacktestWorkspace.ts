import { useBacktestEvents } from '@/utils/useBacktestEvents';
import {
  computed,
  ref,
  watch,
  onMounted,
  onActivated,
  onDeactivated,
  onUnmounted,
} from 'vue';
import { useRouter } from 'vue-router';
import { getBacktestRun } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import {
  useBacktestOverlayStore,
  getBacktestRunSelectability,
} from '@/stores/backtestOverlayStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestRun, Backtest } from '@/types/backtesterContracts';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import { reuseBacktest, reuseRun } from '../backtestReuse';
import { runName } from '../backtestWorkspaceRuns';
import { type HistoryEntry, rowKey } from './backtestHistoryRows';
import { useBacktestHistory } from './useBacktestHistory';
import { useBacktestHistoryRefresh } from './useBacktestHistoryRefresh';
import { useWorkspaceAnalysis } from './useWorkspaceAnalysis';
import { useWorkspaceCommands } from './useWorkspaceCommands';
import { executionLogAvailable } from './workspaceExecution';
import { errorMessage } from './workspaceErrors';
// Created once by the kept-alive view so section rendering never owns state.
export function useBacktestWorkspace() {
  const router = useRouter();
  const workspaceStore = useBacktestWorkspaceStore();
  const overlayStore = useBacktestOverlayStore();
  const marketsStore = useMarketsStore();
  const queueHealth = ref<InstanceType<typeof BacktestQueueHealth> | null>(
    null,
  );
  const detailError = ref<string | null>(null);
  const selectionNotice = ref<string | null>(null);
  const backtestMembers = ref<BacktestRun[]>([]);
  const selectedBacktestId = ref<string | null>(null);
  const selectedRunId = computed(() => workspaceStore.selectedRunId);
  const selectedRun = computed(() => workspaceStore.selectedRun);
  const inspection = useWorkspaceAnalysis(backtestMembers);
  const { selectedComparisonIds, loadAnalysis, setComparison } = inspection;
  const historyRefresh = useBacktestHistoryRefresh(reconcileHistory);
  const { backtests, isLoading, isRefreshing, readError, loadHistory } =
    historyRefresh;
  const history = {
    ...useBacktestHistory(backtests),
    backtests,
    isLoading,
    isRefreshing,
    readError,
  };
  const commands = useWorkspaceCommands({
    selectedBacktestId,
    receiveMembers,
    refreshWorkspace,
    refreshQueue,
    loadHistory,
    onBacktestDeleted,
  });
  const creationOpen = ref(false);
  const creationSession = ref(0);
  const page = ref<'history' | 'analysis'>('history');
  function backToHistory(): void {
    page.value = 'history';
    void router.push('/backtests');
  }
  function showAnalysis(id: string): void {
    page.value = 'analysis';
    void router.push(`/backtests/${encodeURIComponent(id)}`);
  }
  const logRun = ref<BacktestRun | null>(null);
  const openingChartRunId = ref<string | null>(null);
  function chartUnavailableReason(run: BacktestRun): string | null {
    return marketsStore.all.length === 0
      ? getBacktestRunSelectability(run).reason
      : overlayStore.getBacktestRunSelectability(run).reason;
  }
  let detailSequence = 0;
  let pendingDetailId: string | null = null;
  let isActive = false;
  async function loadSelected(
    runId: string,
    background = false,
  ): Promise<void> {
    if (background && pendingDetailId === runId) return;
    pendingDetailId = runId;
    const sequence = ++detailSequence;
    try {
      const detail = await getBacktestRun(runId);
      if (
        sequence === detailSequence &&
        workspaceStore.selectedRunId === runId
      ) {
        if (
          JSON.stringify(workspaceStore.selectedRun) !== JSON.stringify(detail)
        ) {
          workspaceStore.selectRun(detail);
        }
        detailError.value = null;
      }
    } catch (error) {
      if (
        sequence === detailSequence &&
        workspaceStore.selectedRunId === runId
      ) {
        detailError.value = errorMessage(error);
      }
    } finally {
      if (sequence === detailSequence) {
        pendingDetailId = null;
      }
    }
  }

  function receiveMembers(backtestId: string, members: BacktestRun[]): void {
    if (backtestId !== selectedBacktestId.value) return;
    const changed =
      JSON.stringify(backtestMembers.value) !== JSON.stringify(members);
    if (changed) backtestMembers.value = members;
    if (logRun.value?.backtest_id === backtestId) {
      const updatedLogRun = members.find(
        (run) => run.run_id === logRun.value?.run_id,
      );
      logRun.value =
        updatedLogRun && executionLogAvailable(updatedLogRun)
          ? updatedLogRun
          : null;
    }
    const eligible = selectedComparisonIds.value.filter((id) =>
      members.some((run) => run.run_id === id && run.status === 'succeeded'),
    );
    setComparison(eligible);
    const selected = members.find((run) => run.run_id === selectedRunId.value);
    if (selected && changed) workspaceStore.selectRun(selected);
  }

  function reconcileHistory(latestBacktests: Backtest[]): void {
    if (
      overlayStore.selectedRun &&
      !latestBacktests.some(
        (backtest) =>
          backtest.backtest_id === overlayStore.selectedRun?.backtest_id,
      )
    ) {
      overlayStore.clearOverlay();
      selectionNotice.value =
        'The chart overlay was cleared because its Backtest is unavailable.';
    }
    if (
      selectedBacktestId.value &&
      router.currentRoute?.value.params.id !== selectedBacktestId.value &&
      !latestBacktests.some(
        (backtest) => backtest.backtest_id === selectedBacktestId.value,
      )
    ) {
      resetInspection(null);
      selectionNotice.value = 'The selected Backtest is no longer available.';
    }
    if (selectedBacktestId.value && selectedRunId.value)
      void loadSelected(selectedRunId.value, true);
  }
  function redirectUnavailableBacktest(backtestId: string): void {
    if (selectedBacktestId.value === backtestId) {
      resetInspection(null);
      logRun.value = null;
    }
    if (router.currentRoute?.value.params.id === backtestId) {
      void router.replace('/');
    }
  }
  function resetInspection(backtestId: string | null): void {
    // Reopening the same ID does not trigger the overview's member loader.
    if (selectedBacktestId.value !== backtestId) backtestMembers.value = [];
    selectedBacktestId.value = backtestId;
    workspaceStore.clearSelection();
    ++detailSequence;
    setComparison([]);
  }
  function refreshWorkspace(): Promise<void> {
    isRefreshing.value = true;
    if (selectedComparisonIds.value.length) loadAnalysis(true);
    void queueHealth.value?.refresh();
    return loadHistory();
  }

  function selectRun(run: BacktestRun): void {
    workspaceStore.selectRun(run);
    if (
      selectedBacktestId.value === null ||
      selectedComparisonIds.value.length === 0
    ) {
      setComparison(run.status === 'succeeded' ? [run.run_id] : []);
    }
    void loadSelected(run.run_id);
  }

  function createFrom(entry: HistoryEntry): void {
    workspaceStore.createFromSaved(reuseBacktest(entry.backtest));
    creationOpen.value = true;
  }

  function finishCreation(): void {
    creationOpen.value = false;
    workspaceStore.clearCreationDraft();
    creationSession.value += 1;
  }

  async function createdBacktest(backtestId: string): Promise<void> {
    finishCreation();
    resetInspection(backtestId);
    showAnalysis(backtestId);
    await refreshWorkspace();
  }

  function createFromRun(run: BacktestRun): void {
    workspaceStore.createFromSaved(reuseRun(run, marketsStore.all));
    creationOpen.value = true;
  }
  function historyRowProps(entry: HistoryEntry): Record<string, unknown> {
    const select = () => {
      selectionNotice.value = null;
      showAnalysis(rowKey(entry));
      resetInspection(entry.backtest.backtest_id);
    };
    return {
      'data-testid': `workspace-backtest-${entry.backtest.backtest_id}`,
      'aria-selected': selectedBacktestId.value === entry.backtest.backtest_id,
      style: { cursor: 'pointer' },
      tabindex: 0,
      onClick: select,
      onKeydown: (event: KeyboardEvent) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          select();
        }
      },
    };
  }

  function refreshQueue(): void {
    void queueHealth.value?.refresh();
  }
  function onBacktestDeleted(backtest: Backtest): void {
    const overlayBelongsToBacktest =
      overlayStore.selectedRun?.backtest_id === backtest.backtest_id ||
      backtestMembers.value.some(
        (member) => member.run_id === overlayStore.selectedRunId,
      );
    if (selectedBacktestId.value === backtest.backtest_id) {
      resetInspection(null);
      logRun.value = null;
      selectionNotice.value = 'The deleted Backtest is no longer selected.';
    }
    if (overlayBelongsToBacktest) {
      overlayStore.clearOverlay();
      selectionNotice.value =
        'The deleted Backtest was removed from the chart overlay.';
    }
    redirectUnavailableBacktest(backtest.backtest_id);
  }
  async function openOnChart(run: BacktestRun): Promise<void> {
    if (
      openingChartRunId.value !== null ||
      overlayStore.isLoading ||
      chartUnavailableReason(run)
    )
      return;
    openingChartRunId.value = run.run_id;
    selectionNotice.value = null;
    try {
      if (marketsStore.all.length === 0) await marketsStore.fetch();
      const selection = await overlayStore.selectRun(run);
      if (selection.selectable) await router.push('/');
    } catch (error) {
      selectionNotice.value =
        `Could not open run ${runName(run)} on chart: ` + errorMessage(error);
    } finally {
      openingChartRunId.value = null;
    }
  }

  function startUpdates(): void {
    if (isActive) return;
    isActive = true;
    historyRefresh.start();
    if (marketsStore.all.length === 0) void marketsStore.fetch();
    void loadHistory();
    loadAnalysis();
  }

  function stopUpdates(): void {
    isActive = false;
    historyRefresh.stop();
    ++detailSequence;
    pendingDetailId = null;
    inspection.stop();
    logRun.value = null;
  }

  watch(
    () => router.currentRoute?.value.params,
    async (params) => {
      if (!params) return;
      if (!params.id) {
        page.value = 'history';
        return;
      }
      const id = String(params.id);
      page.value = 'analysis';
      if (selectedBacktestId.value === id) return;
      resetInspection(id);
    },
    { immediate: true },
  );

  useBacktestEvents(() => {
    void loadHistory();
  });
  onMounted(startUpdates);
  onActivated(startUpdates);
  onDeactivated(stopUpdates);
  onUnmounted(stopUpdates);
  return {
    history,
    historyActions: {
      create: () => {
        creationOpen.value = true;
      },
      createFrom,
      rowProps: historyRowProps,
      cancelRun: commands.cancelRun,
      deleteBacktest: commands.deleteBacktest,
      cancellingRunIds: commands.cancellingRunIds,
      deletingBacktestIds: commands.deletingBacktestIds,
    },
    inspection,
    commands,
    overlayStore,
    selectedRunId,
    selectedRun,
    selectedBacktestId,
    backtestMembers,
    detailError,
    selectionNotice,
    creationOpen,
    creationSession,
    page,
    queueHealth,
    logRun,
    openingChartRunId,
    backToHistory,
    showAnalysis,
    refreshWorkspace,
    selectRun,
    receiveMembers,
    redirectUnavailableBacktest,
    createFrom,
    createFromRun,
    createdBacktest,
    historyRowProps,
    chartUnavailableReason,
    openOnChart,
  };
}
export type BacktestWorkspace = ReturnType<typeof useBacktestWorkspace>;
