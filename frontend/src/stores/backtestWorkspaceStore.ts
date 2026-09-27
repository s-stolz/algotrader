import { defineStore } from 'pinia';
import { ref } from 'vue';

import type { BacktestRun, BacktestRequestPayload, SweepDraftState } from '@/types/backtesterContracts';
import type { ReuseDraft, ReuseSource } from '@/views/backtestReuse';

export const useBacktestWorkspaceStore = defineStore('backtestWorkspace', () => {
  const selectedRunId = ref<string | null>(null);
  const selectedRun = ref<BacktestRun | null>(null);
  const creationDraft = ref<BacktestRequestPayload | null>(null);
  const creationSweepDraft = ref<SweepDraftState | null>(null);
  const reuseSource = ref<ReuseSource | null>(null);
  const reuseRevision = ref(0);

  function createFromSaved(saved: ReuseDraft): void {
    creationDraft.value = JSON.parse(JSON.stringify(saved.request)) as BacktestRequestPayload;
    creationSweepDraft.value = JSON.parse(JSON.stringify(saved.sweep)) as SweepDraftState;
    reuseSource.value = JSON.parse(JSON.stringify(saved.source)) as ReuseSource;
    reuseRevision.value += 1;
  }

  function selectRun(run: BacktestRun): void {
    selectedRunId.value = run.run_id;
    selectedRun.value = run;
  }

  function clearSelection(): void {
    selectedRunId.value = null;
    selectedRun.value = null;
  }

  return { selectedRunId, selectedRun, creationDraft, creationSweepDraft, reuseSource,
    reuseRevision, createFromSaved, selectRun, clearSelection };
});
