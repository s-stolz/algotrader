import { defineStore } from 'pinia';
import { ref } from 'vue';
import { renameExperiment } from '@/api/backtesterClient';

import type { BacktestBatch, BacktestRun, BacktestCreationRequest, SweepDraftState } from '@/types/backtesterContracts';
import type { ReuseDraft, ReuseSource } from '@/views/backtestReuse';

export const useBacktestWorkspaceStore = defineStore('backtestWorkspace', () => {
  const selectedRunId = ref<string | null>(null);
  const selectedRun = ref<BacktestRun | null>(null);
  const creationDraft = ref<BacktestCreationRequest | null>(null);
  const creationSweepDraft = ref<SweepDraftState | null>(null);
  const reuseSource = ref<ReuseSource | null>(null);
  const reuseRevision = ref(0);

  const nameRevision = ref(0);
  type AcknowledgedName = { name: string | null; revision: number; awaitingRead: boolean };
  const runNames = new Map<string, AcknowledgedName>();
  const batchNames = new Map<string, AcknowledgedName>();

  function preserveName<T extends { name?: string | null }>(
    record: T, saved: AcknowledgedName | undefined, readRevision: number,
  ): T {
    if (!saved) return record;
    if (readRevision >= saved.revision && record.name === saved.name) saved.awaitingRead = false;
    // Local projections cannot confirm readback; captured read revisions protect older responses.
    return saved.awaitingRead || (readRevision >= 0 && readRevision < saved.revision)
      ? { ...record, name: saved.name } : record;
  }

  function preserveRunName(run: BacktestRun, readRevision = -1): BacktestRun {
    return preserveName(run, runNames.get(run.run_id), readRevision);
  }

  function preserveBatchName(batch: BacktestBatch, readRevision = -1): BacktestBatch {
    return preserveName(batch, batchNames.get(batch.batch_id), readRevision);
  }

  const pendingNameSaves = new Map<string, Promise<string | null>>();
  function saveName(kind: 'run' | 'batch', id: string, name: string | null): Promise<string | null> {
    const key = `${kind}:${id}`;
    const previous = pendingNameSaves.get(key);
    const pending = (async () => {
      if (previous) await previous.catch(() => undefined);
      const authoritative = await renameExperiment(kind, id, name);
      acknowledgeName(kind, id, authoritative);
      return authoritative;
    })();
    pendingNameSaves.set(key, pending);
    void pending.finally(() => {
      if (pendingNameSaves.get(key) === pending) pendingNameSaves.delete(key);
    }).catch(() => undefined);
    return pending;
  }

  function acknowledgeName(kind: 'run' | 'batch', id: string, name: string | null): void {
    const revision = nameRevision.value + 1;
    (kind === 'run' ? runNames : batchNames).set(id, { name, revision, awaitingRead: true });
    if (kind === 'run' && selectedRun.value?.run_id === id) {
      selectedRun.value = { ...selectedRun.value, name };
    }
    nameRevision.value = revision;
  }

  function createFromSaved(saved: ReuseDraft): void {
    creationDraft.value = JSON.parse(JSON.stringify(saved.request)) as BacktestCreationRequest;
    creationSweepDraft.value = JSON.parse(JSON.stringify(saved.sweep)) as SweepDraftState;
    reuseSource.value = JSON.parse(JSON.stringify(saved.source)) as ReuseSource;
    reuseRevision.value += 1;
  }

  function selectRun(run: BacktestRun): void {
    selectedRunId.value = run.run_id;
    selectedRun.value = preserveRunName(run);
  }

  function clearSelection(): void {
    selectedRunId.value = null;
    selectedRun.value = null;
  }

  return { selectedRunId, selectedRun, creationDraft, creationSweepDraft, reuseSource,
    reuseRevision, nameRevision, saveName, acknowledgeName, preserveRunName, preserveBatchName, createFromSaved, selectRun, clearSelection };
});
