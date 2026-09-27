import { defineStore } from 'pinia';
import { ref } from 'vue';

import type { BacktestRun, BacktestRequestPayload, SweepDraftState } from '@/types/backtesterContracts';

export const useBacktestWorkspaceStore = defineStore('backtestWorkspace', () => {
  const selectedRunId = ref<string | null>(null);
  const selectedRun = ref<BacktestRun | null>(null);
  const creationDraft = ref<BacktestRequestPayload | null>(null);
  const creationSweepDraft = ref<SweepDraftState | null>(null);

  function selectRun(run: BacktestRun): void {
    selectedRunId.value = run.run_id;
    selectedRun.value = run;
  }

  function clearSelection(): void {
    selectedRunId.value = null;
    selectedRun.value = null;
  }

  return { selectedRunId, selectedRun, creationDraft, creationSweepDraft, selectRun, clearSelection };
});
