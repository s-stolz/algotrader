import { defineStore } from 'pinia';
import { ref } from 'vue';
import { renameExperiment } from '@/api/backtesterClient';

import type {
  Backtest,
  BacktestRun,
  BacktestCreationRequest,
  BacktestSelectionsDraft,
} from '@/types/backtesterContracts';
import type { ReuseDraft, ReuseSource } from '@/views/backtestReuse';

export const useBacktestWorkspaceStore = defineStore(
  'backtestWorkspace',
  () => {
    const selectedRunId = ref<string | null>(null);
    const selectedRun = ref<BacktestRun | null>(null);
    const creationDraft = ref<BacktestCreationRequest | null>(null);
    const creationSelections = ref<BacktestSelectionsDraft | null>(null);
    const reuseSource = ref<ReuseSource | null>(null);
    const reuseRevision = ref(0);

    const nameRevision = ref(0);
    type AcknowledgedName = {
      name: string | null;
      revision: number;
      awaitingRead: boolean;
    };
    const backtestNames = new Map<string, AcknowledgedName>();

    function preserveName<T extends { name?: string | null }>(
      record: T,
      saved: AcknowledgedName | undefined,
      readRevision: number,
    ): T {
      if (!saved) return record;
      if (readRevision >= saved.revision && record.name === saved.name)
        saved.awaitingRead = false;
      // Local projections cannot confirm readback; captured read revisions protect older responses.
      return saved.awaitingRead ||
        (readRevision >= 0 && readRevision < saved.revision)
        ? { ...record, name: saved.name }
        : record;
    }

    function preserveBacktestName(
      backtest: Backtest,
      readRevision = -1,
    ): Backtest {
      return preserveName(
        backtest,
        backtestNames.get(backtest.backtest_id),
        readRevision,
      );
    }

    const pendingNameSaves = new Map<string, Promise<string | null>>();
    function saveName(id: string, name: string | null): Promise<string | null> {
      const key = id;
      const previous = pendingNameSaves.get(key);
      const pending = (async () => {
        if (previous) await previous.catch(() => undefined);
        const authoritative = await renameExperiment(id, name);
        acknowledgeName(id, authoritative);
        return authoritative;
      })();
      pendingNameSaves.set(key, pending);
      void pending
        .finally(() => {
          if (pendingNameSaves.get(key) === pending)
            pendingNameSaves.delete(key);
        })
        .catch(() => undefined);
      return pending;
    }

    function acknowledgeName(id: string, name: string | null): void {
      const revision = nameRevision.value + 1;
      backtestNames.set(id, {
        name,
        revision,
        awaitingRead: true,
      });
      nameRevision.value = revision;
    }

    function createFromSaved(saved: ReuseDraft): void {
      creationDraft.value = JSON.parse(
        JSON.stringify(saved.request),
      ) as BacktestCreationRequest;
      creationSelections.value = JSON.parse(
        JSON.stringify(saved.selections),
      ) as BacktestSelectionsDraft;
      reuseSource.value = JSON.parse(
        JSON.stringify(saved.source),
      ) as ReuseSource;
      reuseRevision.value += 1;
    }

    function clearCreationDraft(): void {
      creationDraft.value = null;
      creationSelections.value = null;
      reuseSource.value = null;
    }

    function selectRun(run: BacktestRun): void {
      selectedRunId.value = run.run_id;
      selectedRun.value = run;
    }

    function clearSelection(): void {
      selectedRunId.value = null;
      selectedRun.value = null;
    }

    return {
      selectedRunId,
      selectedRun,
      creationDraft,
      creationSelections,
      reuseSource,
      reuseRevision,
      nameRevision,
      saveName,
      acknowledgeName,
      preserveBacktestName,
      createFromSaved,
      clearCreationDraft,
      selectRun,
      clearSelection,
    };
  },
);
