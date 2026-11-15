import { computed, ref, shallowRef, watch } from 'vue';
import { defineStore } from 'pinia';
import { fetchExecutionLog } from '@/api/executionLogClient';
import type { BacktestRun } from '@/types/backtesterContracts';
import {
  EXECUTION_LOG_PAGE_SIZE,
  type ExecutionLogItem,
} from '@/types/backtest/executionLog';

export interface ExecutionLogSelection {
  run_id: string;
  backtest_id: string;
  run_ordinal: number;
  symbols: string[];
  currency: string | null;
}
export const useExecutionLogStore = defineStore('executionLog', () => {
  const selectedRun = shallowRef<ExecutionLogSelection | null>(null);
  const isOpen = ref(false);
  const splitSize = ref(0.48);
  const page = ref(1);
  const includeUnexecuted = ref(false);
  const items = shallowRef<ExecutionLogItem[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const consumesSpace = computed(
    () => isOpen.value && selectedRun.value !== null,
  );
  let hasLoaded = false;
  let generation = 0;
  let request: AbortController | null = null;

  async function load(): Promise<void> {
    const run = selectedRun.value;
    if (!run || !isOpen.value) return;
    const current = ++generation;
    request?.abort();
    request = new AbortController();
    items.value = [];
    loading.value = true;
    error.value = null;
    try {
      const result = await fetchExecutionLog(
        run.run_id,
        page.value,
        includeUnexecuted.value,
        request.signal,
      );
      if (current !== generation) return;
      items.value = result.items;
      total.value = result.total;
      hasLoaded = true;
    } catch (reason) {
      if (current !== generation) return;
      error.value =
        reason instanceof Error ? reason.message : 'Execution log unavailable.';
    } finally {
      if (current === generation) loading.value = false;
    }
  }
  function selectRun(run: BacktestRun, open = true): void {
    isOpen.value = open;
    if (selectedRun.value?.run_id === run.run_id) {
      if (error.value) void load();
      return;
    }
    ++generation;
    request?.abort();
    loading.value = false;
    error.value = null;
    items.value = [];
    hasLoaded = false;
    selectedRun.value = {
      run_id: run.run_id,
      backtest_id: run.backtest_id,
      run_ordinal: run.run_ordinal,
      symbols: [...run.request.symbols],
      currency: run.request.instrument?.settlement_currency ?? null,
    };
    page.value = 1;
    total.value = 0;
    includeUnexecuted.value = false;
    void load();
  }
  function setPage(value: number): void {
    if (
      !Number.isSafeInteger(value) ||
      value < 1 ||
      value > Math.max(1, Math.ceil(total.value / EXECUTION_LOG_PAGE_SIZE)) ||
      value === page.value
    )
      return;
    page.value = value;
    hasLoaded = false;
    void load();
  }
  function setIncludeUnexecuted(value: boolean): void {
    if (value === includeUnexecuted.value) return;
    hasLoaded = false;
    includeUnexecuted.value = value;
    page.value = 1;
    total.value = 0;
    void load();
  }
  function clear(): void {
    ++generation;
    request?.abort();
    request = null;
    selectedRun.value = null;
    isOpen.value = false;
    items.value = [];
    total.value = 0;
    loading.value = false;
    error.value = null;
  }
  watch(consumesSpace, (visible) => {
    if (visible && !hasLoaded && !loading.value) void load();
  });
  function resize(value: number | string): void {
    const ratio = Number(value);
    if (Number.isFinite(ratio))
      splitSize.value = Math.max(0.2, Math.min(0.8, ratio));
  }
  return {
    selectedRun,
    isOpen,
    splitSize,
    consumesSpace,
    page,
    includeUnexecuted,
    items,
    total,
    loading,
    error,
    selectRun,
    setPage,
    setIncludeUnexecuted,
    clear,
    resize,
    retry: load,
  };
});
