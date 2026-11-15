import { ref, shallowRef, watch } from 'vue';
import { listBacktests } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { Backtest } from '@/types/backtesterContracts';
import { errorMessage } from './workspaceErrors';
export function useBacktestHistoryRefresh(
  onHistory: (backtests: Backtest[]) => void,
) {
  const workspaceStore = useBacktestWorkspaceStore();
  const backtests = shallowRef<Backtest[] | null>(null);
  const isLoading = ref(false);
  const isRefreshing = ref(false);
  const readError = ref<string | null>(null);
  let readGeneration = 0;
  let activeHistoryRead: Promise<void> | null = null;
  let refreshAfterCurrentRead = false;
  let isActive = false;
  async function readHistory(): Promise<void> {
    const generation = ++readGeneration;
    const nameReadRevision = workspaceStore.nameRevision;
    isLoading.value = backtests.value === null;

    try {
      const readBacktestRecords = await listBacktests();
      if (generation !== readGeneration || !isActive) return;
      const latestBacktests = readBacktestRecords.map((backtest) =>
        workspaceStore.preserveBacktestName(backtest, nameReadRevision),
      );
      backtests.value = latestBacktests;
      readError.value = null;
      onHistory(latestBacktests);
    } catch (error) {
      if (generation === readGeneration && isActive)
        readError.value = errorMessage(error);
    } finally {
      if (generation !== readGeneration) return;
      activeHistoryRead = null;
      if (refreshAfterCurrentRead && isActive) {
        refreshAfterCurrentRead = false;
        void loadHistory();
        return;
      }
      isLoading.value = false;
      isRefreshing.value = false;
    }
  }

  function loadHistory(shouldQueue = true): Promise<void> {
    if (!isActive) return Promise.resolve();
    if (activeHistoryRead) {
      if (shouldQueue) refreshAfterCurrentRead = true;
      return activeHistoryRead;
    }
    activeHistoryRead = readHistory();
    return activeHistoryRead;
  }

  watch(
    () => workspaceStore.nameRevision,
    () => {
      if (backtests.value)
        backtests.value = backtests.value.map((backtest) =>
          workspaceStore.preserveBacktestName(backtest, -1),
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
    backtests,
    isLoading,
    isRefreshing,
    readError,
    loadHistory,
    start,
    stop,
  };
}
