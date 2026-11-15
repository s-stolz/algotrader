import { computed, ref, watch, onScopeDispose, type Ref } from 'vue';
import { fetchBacktestClosedTrades } from '@/api/backtesterClient';
import type { BacktestRun } from '@/types/backtesterContracts';
import { summarizeTrades, type RunResults } from './runResults';
import { decodeProfitFactor } from '@/types/backtest/results';
import { errorMessage } from '../workspaceErrors';
export interface RunResultState {
  status: 'loading' | 'ready' | 'error';
  result?: RunResults;
  error?: string;
}
export function useRunResults(runs: Ref<BacktestRun[]>) {
  const states = ref<Record<string, RunResultState>>({});
  const ids = computed(() =>
    runs.value
      .filter((run) => run.status === 'succeeded')
      .map((run) => run.run_id),
  );
  const requests = new Map<string, symbol>();
  let active = true;
  let inflight = 0;
  function pump() {
    if (!active) return;
    while (inflight < 4) {
      const id = ids.value.find(
        (id) => states.value[id]?.status === 'loading' && !requests.has(id),
      );
      if (!id) return;
      const token = Symbol(id);
      requests.set(id, token);
      inflight++;
      void (async () => {
        try {
          const trades = await fetchBacktestClosedTrades(id);
          if (active && requests.get(id) === token) {
            const run = runs.value.find((run) => run.run_id === id);
            const result = summarizeTrades(
              trades,
              decodeProfitFactor(run?.metrics?.profit_factor),
            );
            states.value[id] = {
              status: 'ready',
              result,
            };
          }
        } catch (error) {
          if (active && requests.get(id) === token)
            states.value[id] = { status: 'error', error: errorMessage(error) };
        } finally {
          if (requests.get(id) === token) requests.delete(id);
          inflight--;
          pump();
        }
      })();
    }
  }
  function reconcile(retry = false) {
    if (!active) return;
    const allowed = new Set(ids.value);
    for (const id of requests.keys()) if (!allowed.has(id)) requests.delete(id);
    states.value = Object.fromEntries(
      Object.entries(states.value).filter(([id]) => allowed.has(id)),
    );
    for (const id of ids.value) {
      if (!states.value[id] || (retry && states.value[id].status === 'error'))
        states.value[id] = { status: 'loading' };
    }
    pump();
  }
  watch(
    () => JSON.stringify(ids.value),
    () => reconcile(),
    { immediate: true },
  );
  function stop() {
    active = false;
    requests.clear();
  }
  function start() {
    if (!active) {
      active = true;
      reconcile();
    }
  }
  onScopeDispose(stop);
  return { states, start, stop, retry: () => reconcile(true) };
}
