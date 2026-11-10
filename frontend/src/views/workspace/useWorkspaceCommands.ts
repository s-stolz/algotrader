import { ref, type Ref } from 'vue';
import {
  cancelBacktestRun,
  deleteBacktest as deleteSavedBacktest,
  listBacktestMembers,
} from '@/api/backtesterClient';
import type { BacktestRun, Backtest } from '@/types/backtesterContracts';
import { errorMessage } from './workspaceErrors';
export function useWorkspaceCommands(context: {
  selectedBacktestId: Ref<string | null>;
  receiveMembers: (id: string, members: BacktestRun[]) => void;
  refreshWorkspace: () => Promise<void>;
  refreshQueue: () => void;
  loadHistory: () => Promise<void>;
  onBacktestDeleted: (backtest: Backtest) => void;
}) {
  const {
    selectedBacktestId,
    receiveMembers,
    refreshWorkspace,
    refreshQueue,
    loadHistory,
    onBacktestDeleted,
  } = context;
  const deleteError = ref<string | null>(null);
  const cancelError = ref<string | null>(null);
  const cancellingRunIds = ref<ReadonlySet<string>>(new Set());
  const deletingBacktestIds = ref<ReadonlySet<string>>(new Set());
  async function cancelRun(run: BacktestRun): Promise<void> {
    if (
      !['queued', 'running'].includes(run.status) ||
      cancellingRunIds.value.has(run.run_id)
    )
      return;
    cancellingRunIds.value = new Set([...cancellingRunIds.value, run.run_id]);
    cancelError.value = null;
    try {
      await cancelBacktestRun(run.run_id);
      await refreshWorkspace();
      if (selectedBacktestId.value === run.backtest_id) {
        receiveMembers(
          run.backtest_id,
          await listBacktestMembers(run.backtest_id, false),
        );
      }
    } catch (error) {
      cancelError.value = errorMessage(error);
      await refreshWorkspace();
    } finally {
      const pending = new Set(cancellingRunIds.value);
      pending.delete(run.run_id);
      cancellingRunIds.value = pending;
    }
  }

  async function deleteBacktest(backtest: Backtest): Promise<void> {
    if (
      !['completed', 'cancelled'].includes(backtest.status) ||
      deletingBacktestIds.value.has(backtest.backtest_id)
    )
      return;
    if (
      !window.confirm(
        'Delete this entire Backtest, all members and saved results? This cannot be undone.',
      )
    )
      return;
    deletingBacktestIds.value = new Set([
      ...deletingBacktestIds.value,
      backtest.backtest_id,
    ]);
    deleteError.value = null;
    try {
      await deleteSavedBacktest(backtest.backtest_id);
      onBacktestDeleted(backtest);
      refreshQueue();
      await loadHistory();
    } catch (error) {
      deleteError.value = errorMessage(error);
    } finally {
      const stillDeleting = new Set(deletingBacktestIds.value);
      stillDeleting.delete(backtest.backtest_id);
      deletingBacktestIds.value = stillDeleting;
    }
  }

  return {
    deleteError,
    cancelError,
    cancellingRunIds,
    deletingBacktestIds,
    cancelRun,
    deleteBacktest,
  };
}
