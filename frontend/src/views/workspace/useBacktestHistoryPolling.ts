import { ref, shallowRef, watch } from 'vue';
import { listBacktestRuns, listBacktestBatches } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { BacktestRun, BacktestBatch } from '@/types/backtesterContracts';
import { errorMessage } from './workspaceErrors';
export function useBacktestHistoryPolling(
  onHistory: (runs: BacktestRun[], batches: BacktestBatch[]) => void,
) {
  const workspaceStore = useBacktestWorkspaceStore();
  const runs = ref<BacktestRun[] | null>(null);
  const batches = shallowRef<BacktestBatch[] | null>(null);
  const isLoading = ref(false);
  const isRefreshing = ref(false);
  const readError = ref<string | null>(null);
  let readGeneration = 0;
  let activeHistoryRead: Promise<void> | null = null;
  let refreshAfterCurrentRead = false;
  let isActive = false;
  async function readRuns(): Promise<void> {
    const generation = ++readGeneration;
    const nameReadRevision = workspaceStore.nameRevision;
    isLoading.value = runs.value === null;

    try {
      const [readRunRecords, readBatchRecords] = await Promise.all([
        listBacktestRuns({ membership: 'standalone' }),
        listBacktestBatches(),
      ]);
      if (generation !== readGeneration || !isActive) return;
      const latest = readRunRecords.map((run) =>
        workspaceStore.preserveRunName(run, nameReadRevision),
      );
      const latestBatches = readBatchRecords.map((batch) =>
        workspaceStore.preserveBatchName(batch, nameReadRevision),
      );
      runs.value = latest;
      batches.value = latestBatches;
      readError.value = null;
      onHistory(latest, latestBatches);
    } catch (error) {
      if (generation === readGeneration && isActive)
        readError.value = errorMessage(error);
    } finally {
      if (generation !== readGeneration) return;
      activeHistoryRead = null;
      if (refreshAfterCurrentRead && isActive) {
        refreshAfterCurrentRead = false;
        void loadRuns();
        return;
      }
      isLoading.value = false;
      isRefreshing.value = false;
    }
  }

  function loadRuns(shouldQueue = true): Promise<void> {
    if (!isActive) return Promise.resolve();
    if (activeHistoryRead) {
      if (shouldQueue) refreshAfterCurrentRead = true;
      return activeHistoryRead;
    }
    activeHistoryRead = readRuns();
    return activeHistoryRead;
  }

  watch(
    () => workspaceStore.nameRevision,
    () => {
      if (runs.value)
        runs.value = runs.value.map((run) =>
          workspaceStore.preserveRunName(run, -1),
        );
      if (batches.value)
        batches.value = batches.value.map((batch) =>
          workspaceStore.preserveBatchName(batch, -1),
        );
    },
  );
  function start() {
    isActive = true;
  }
  function stop() {
    isActive = false;
    ++readGeneration;
    activeHistoryRead = null;
    refreshAfterCurrentRead = false;
    isLoading.value = false;
    isRefreshing.value = false;
  }
  return {
    runs,
    batches,
    isLoading,
    isRefreshing,
    readError,
    loadRuns,
    start,
    stop,
  };
}
