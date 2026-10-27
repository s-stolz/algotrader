import { ref, type Ref } from 'vue';
import {
  cancelBacktestRun,
  deleteBacktestRun,
  deleteBacktestBatch,
  listBacktestBatchMembers,
} from '@/api/backtesterClient';
import type { BacktestRun, BacktestBatch } from '@/types/backtesterContracts';
import { errorMessage } from './workspaceErrors';
export function useWorkspaceCommands(context: {
  selectedBatchId: Ref<string | null>;
  receiveMembers: (id: string, members: BacktestRun[]) => void;
  refreshWorkspace: () => Promise<void>;
  refreshQueue: () => void;
  loadRuns: () => Promise<void>;
  onRunDeleted: (run: BacktestRun) => void;
  onBatchDeleted: (batch: BacktestBatch) => void;
}) {
  const {
    selectedBatchId,
    receiveMembers,
    refreshWorkspace,
    refreshQueue,
    loadRuns,
    onRunDeleted,
    onBatchDeleted,
  } = context;
  const deleteError = ref<string | null>(null);
  const cancelError = ref<string | null>(null);
  const cancellingRunIds = ref<ReadonlySet<string>>(new Set());
  const deletingRunIds = ref<ReadonlySet<string>>(new Set());
  const deletingBatchIds = ref<ReadonlySet<string>>(new Set());
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
      if (run.batch_id && selectedBatchId.value === run.batch_id) {
        receiveMembers(
          run.batch_id,
          await listBacktestBatchMembers(run.batch_id),
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

  async function deleteRun(run: BacktestRun): Promise<void> {
    if (
      !['succeeded', 'failed', 'cancelled'].includes(run.status) ||
      deletingRunIds.value.has(run.run_id)
    )
      return;
    if (
      !window.confirm(
        'Delete this Backtest and all saved results, trades and fills? This cannot be undone.',
      )
    )
      return;
    deletingRunIds.value = new Set([...deletingRunIds.value, run.run_id]);
    deleteError.value = null;
    try {
      await deleteBacktestRun(run.run_id);
      onRunDeleted(run);
      refreshQueue();
      await loadRuns();
    } catch (error) {
      deleteError.value = errorMessage(error);
    } finally {
      const stillDeleting = new Set(deletingRunIds.value);
      stillDeleting.delete(run.run_id);
      deletingRunIds.value = stillDeleting;
    }
  }

  async function deleteBatch(batch: BacktestBatch): Promise<void> {
    if (
      !['completed', 'cancelled'].includes(batch.status) ||
      deletingBatchIds.value.has(batch.batch_id)
    )
      return;
    if (
      !window.confirm(
        'Delete this entire Backtest Batch, all members and saved results? This cannot be undone.',
      )
    )
      return;
    deletingBatchIds.value = new Set([
      ...deletingBatchIds.value,
      batch.batch_id,
    ]);
    deleteError.value = null;
    try {
      await deleteBacktestBatch(batch.batch_id);
      onBatchDeleted(batch);
      refreshQueue();
      await loadRuns();
    } catch (error) {
      deleteError.value = errorMessage(error);
    } finally {
      const stillDeleting = new Set(deletingBatchIds.value);
      stillDeleting.delete(batch.batch_id);
      deletingBatchIds.value = stillDeleting;
    }
  }

  return {
    deleteError,
    cancelError,
    cancellingRunIds,
    deletingRunIds,
    deletingBatchIds,
    cancelRun,
    deleteRun,
    deleteBatch,
  };
}
