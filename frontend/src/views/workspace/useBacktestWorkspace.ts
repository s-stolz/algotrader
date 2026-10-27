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
import type { BacktestRun, BacktestBatch } from '@/types/backtesterContracts';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import { reuseBatch, reuseStandalone } from '../backtestReuse';
import { runName } from '../backtestWorkspaceRuns';
import { type HistoryEntry, rowKey } from './backtestHistoryRows';
import { useBacktestHistory } from './useBacktestHistory';
import { useBacktestHistoryPolling } from './useBacktestHistoryPolling';
import { useWorkspaceAnalysis } from './useWorkspaceAnalysis';
import { useWorkspaceCommands } from './useWorkspaceCommands';
import { executionLogAvailable } from './workspaceExecution';
import { errorMessage } from './workspaceErrors';
// Created once by the kept-alive view so section rendering never owns state.
export function useBacktestWorkspace() {
  const POLL_INTERVAL_MS = 5000;
  const router = useRouter();
  const workspaceStore = useBacktestWorkspaceStore();
  const overlayStore = useBacktestOverlayStore();
  const marketsStore = useMarketsStore();
  const queueHealth = ref<InstanceType<typeof BacktestQueueHealth> | null>(
    null,
  );
  const detailError = ref<string | null>(null);
  const selectionNotice = ref<string | null>(null);
  const batchMembers = ref<BacktestRun[]>([]);
  const selectedBatchId = ref<string | null>(null);
  const selectedRunId = computed(() => workspaceStore.selectedRunId);
  const selectedRun = computed(() => workspaceStore.selectedRun);
  const inspection = useWorkspaceAnalysis({
    selectedBatchId,
    batchMembers,
    selectedRun,
  });
  const { selectedComparisonIds, loadAnalysis, setComparison } = inspection;
  const polling = useBacktestHistoryPolling(reconcileHistory);
  const { runs, batches, isLoading, isRefreshing, readError, loadRuns } =
    polling;
  const history = {
    ...useBacktestHistory(runs, batches),
    runs,
    batches,
    isLoading,
    isRefreshing,
    readError,
  };
  const commands = useWorkspaceCommands({
    selectedBatchId,
    receiveMembers,
    refreshWorkspace,
    refreshQueue,
    loadRuns,
    onRunDeleted,
    onBatchDeleted,
  });
  const creationOpen = ref(false);
  const page = ref<'history' | 'analysis'>('history');
  function backToHistory(): void {
    page.value = 'history';
    void router.push('/backtests');
  }
  function showAnalysis(kind: 'run' | 'batch', id: string): void {
    page.value = 'analysis';
    void router.push(`/backtests/${kind}/${encodeURIComponent(id)}`);
  }
  const logRun = ref<BacktestRun | null>(null);
  const openingChartRunId = ref<string | null>(null);
  function chartUnavailableReason(run: BacktestRun): string | null {
    return marketsStore.all.length === 0
      ? getBacktestRunSelectability(run).reason
      : overlayStore.getBacktestRunSelectability(run).reason;
  }
  let pollTimer: ReturnType<typeof setInterval> | null = null;
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
    const nameReadRevision = workspaceStore.nameRevision;
    try {
      const detail = workspaceStore.preserveRunName(
        await getBacktestRun(runId),
        nameReadRevision,
      );
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

  function receiveMembers(batchId: string, members: BacktestRun[]): void {
    if (batchId !== selectedBatchId.value) return;
    const changed =
      JSON.stringify(batchMembers.value) !== JSON.stringify(members);
    if (changed) batchMembers.value = members;
    if (logRun.value?.batch_id === batchId) {
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

  function reconcileHistory(
    latest: BacktestRun[],
    latestBatches: BacktestBatch[],
  ): void {
    if (logRun.value && !logRun.value.batch_id) {
      const updatedLogRun = latest.find(
        (run) => run.run_id === logRun.value?.run_id,
      );
      logRun.value =
        updatedLogRun && executionLogAvailable(updatedLogRun)
          ? updatedLogRun
          : null;
    }
    if (
      (overlayStore.selectedRun?.batch_id &&
        !latestBatches.some(
          (batch) => batch.batch_id === overlayStore.selectedRun?.batch_id,
        )) ||
      (overlayStore.selectedRun &&
        !overlayStore.selectedRun.batch_id &&
        !latest.some((run) => run.run_id === overlayStore.selectedRunId))
    ) {
      overlayStore.clearOverlay();
      selectionNotice.value =
        'The chart overlay was cleared because its saved Backtest is unavailable.';
    }
    if (
      selectedBatchId.value &&
      !latestBatches.some((batch) => batch.batch_id === selectedBatchId.value)
    ) {
      selectedBatchId.value = null;
      batchMembers.value = [];
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
      selectionNotice.value =
        'The selected Backtest Batch is no longer available.';
    }
    const selected = latest.find((run) => run.run_id === selectedRunId.value);
    if (selected) {
      const changed =
        JSON.stringify(selectedRun.value) !== JSON.stringify(selected);
      if (changed) workspaceStore.selectRun(selected);
      void loadSelected(selected.run_id, true);
      if (changed) setComparison(selectedComparisonIds.value);
    } else if (selectedBatchId.value && selectedRunId.value) {
      void loadSelected(selectedRunId.value, true);
    } else if (selectedRunId.value) {
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
      selectionNotice.value =
        'The selected Backtest Run is no longer available.';
    }
  }
  function refreshWorkspace(): Promise<void> {
    isRefreshing.value = true;
    if (selectedComparisonIds.value.length) loadAnalysis(true);
    void queueHealth.value?.refresh();
    return loadRuns();
  }

  function selectRun(run: BacktestRun): void {
    workspaceStore.selectRun(run);
    if (
      selectedBatchId.value === null ||
      selectedComparisonIds.value.length === 0
    ) {
      setComparison(run.status === 'succeeded' ? [run.run_id] : []);
    }
    void loadSelected(run.run_id);
  }

  function createFrom(entry: HistoryEntry): void {
    workspaceStore.createFromSaved(
      entry.kind === 'run'
        ? reuseStandalone(entry.run)
        : reuseBatch(entry.batch),
    );
    creationOpen.value = true;
  }

  async function createdBatch(batchId: string): Promise<void> {
    selectedBatchId.value = batchId;
    batchMembers.value = [];
    workspaceStore.clearSelection();
    ++detailSequence;
    setComparison([]);
    showAnalysis('batch', batchId);
    await refreshWorkspace();
  }

  async function createdRun(runId: string): Promise<void> {
    void queueHealth.value?.refresh();
    try {
      selectedBatchId.value = null;
      batchMembers.value = [];
      selectRun(await getBacktestRun(runId));
      showAnalysis('run', runId);
      detailError.value = null;
    } catch (error) {
      detailError.value = errorMessage(error);
    }
    await loadRuns();
  }

  function historyRowProps(entry: HistoryEntry): Record<string, unknown> {
    const isRun = entry.kind === 'run';
    const select = () => {
      selectionNotice.value = null;
      showAnalysis(entry.kind, rowKey(entry));
      if (entry.kind === 'run') {
        selectedBatchId.value = null;
        batchMembers.value = [];
        selectRun(entry.run);
      } else {
        selectedBatchId.value = entry.batch.batch_id;
        batchMembers.value = [];
        workspaceStore.clearSelection();
        ++detailSequence;
        setComparison([]);
      }
    };
    return {
      'data-testid': isRun
        ? `workspace-run-${entry.run.run_id}`
        : `workspace-batch-${entry.batch.batch_id}`,
      'aria-selected': isRun
        ? selectedRunId.value === entry.run.run_id
        : selectedBatchId.value === entry.batch.batch_id,
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
  function onRunDeleted(run: BacktestRun): void {
    if (logRun.value?.run_id === run.run_id) logRun.value = null;
    if (selectedRunId.value === run.run_id) {
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
    }
    if (overlayStore.selectedRunId === run.run_id) {
      overlayStore.clearOverlay();
      selectionNotice.value =
        'The deleted Backtest Run was removed from the chart overlay.';
    }
  }
  function onBatchDeleted(batch: BacktestBatch): void {
    const overlayBelongsToBatch =
      overlayStore.selectedRun?.batch_id === batch.batch_id ||
      batchMembers.value.some(
        (member) => member.run_id === overlayStore.selectedRunId,
      );
    if (selectedBatchId.value === batch.batch_id) {
      selectedBatchId.value = null;
      batchMembers.value = [];
      workspaceStore.clearSelection();
      ++detailSequence;
      setComparison([]);
      logRun.value = null;
      selectionNotice.value =
        'The deleted Backtest Batch is no longer selected.';
    }
    if (overlayBelongsToBatch) {
      overlayStore.clearOverlay();
      selectionNotice.value =
        'The deleted Backtest Batch was removed from the chart overlay.';
    }
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

  function startPolling(): void {
    if (isActive) return;
    isActive = true;
    polling.start();
    if (marketsStore.all.length === 0) void marketsStore.fetch();
    void loadRuns();
    loadAnalysis();
    pollTimer = setInterval(() => {
      void loadRuns(false);
    }, POLL_INTERVAL_MS);
  }

  function stopPolling(): void {
    isActive = false;
    polling.stop();
    ++detailSequence;
    pendingDetailId = null;
    inspection.stop();
    logRun.value = null;
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
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
      if (params.kind === 'batch') {
        if (selectedBatchId.value === id) return;
        selectedBatchId.value = id;
        batchMembers.value = [];
        workspaceStore.clearSelection();
        ++detailSequence;
        setComparison([]);
      } else if (
        params.kind === 'run' &&
        (selectedBatchId.value || selectedRunId.value !== id)
      ) {
        selectedBatchId.value = null;
        batchMembers.value = [];
        workspaceStore.clearSelection();
        setComparison([]);
        const sequence = ++detailSequence;
        const nameReadRevision = workspaceStore.nameRevision;
        try {
          const run = workspaceStore.preserveRunName(
            await getBacktestRun(id),
            nameReadRevision,
          );
          if (sequence !== detailSequence) return;
          selectRun(run);
        } catch (error) {
          if (sequence === detailSequence)
            detailError.value = errorMessage(error);
        }
      }
    },
    { immediate: true },
  );

  onMounted(startPolling);
  onActivated(startPolling);
  onDeactivated(stopPolling);
  onUnmounted(stopPolling);
  return {
    history,
    historyActions: {
      create: () => {
        creationOpen.value = true;
      },
      createFrom,
      rowProps: historyRowProps,
      cancelRun: commands.cancelRun,
      deleteRun: commands.deleteRun,
      deleteBatch: commands.deleteBatch,
      cancellingRunIds: commands.cancellingRunIds,
      deletingRunIds: commands.deletingRunIds,
      deletingBatchIds: commands.deletingBatchIds,
    },
    inspection,
    commands,
    overlayStore,
    selectedRunId,
    selectedRun,
    selectedBatchId,
    batchMembers,
    detailError,
    selectionNotice,
    creationOpen,
    page,
    queueHealth,
    logRun,
    openingChartRunId,
    backToHistory,
    refreshWorkspace,
    selectRun,
    receiveMembers,
    createFrom,
    createdRun,
    createdBatch,
    historyRowProps,
    chartUnavailableReason,
    openOnChart,
  };
}
export type BacktestWorkspace = ReturnType<typeof useBacktestWorkspace>;
