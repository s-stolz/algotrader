import { defineStore } from 'pinia';
import { ref, shallowRef } from 'vue';
import type { Router } from 'vue-router';
import { useBacktestOverlayStore } from './backtestOverlayStore';
import { useMarketsStore } from './marketsStore';
import { useCurrentMarketStore } from './currentMarketStore';
import { useCurrentTimeframeStore } from './currentTimeframeStore';

export const useTradeNavigationStore = defineStore('tradeNavigation', () => {
  const destination = shallowRef<{
    id: number;
    runId: string;
    timestampMs: number;
  } | null>(null);
  const revision = ref(0);
  const loading = ref(false);
  const preparing = ref(false);
  function cancel() {
    revision.value += 1;
    destination.value = null;
    loading.value = false;
    preparing.value = false;
  }
  async function open(runId: string, timestampMs: number, router: Router) {
    cancel();
    preparing.value = true;
    const id = revision.value;
    let navigating = false;
    const removeGuard = router.afterEach(() => {
      if (!navigating && revision.value === id) cancel();
    });
    const isCurrent = () => revision.value === id;
    try {
      const markets = useMarketsStore();
      const overlay = useBacktestOverlayStore();
      if (!markets.all.length) await markets.fetch();
      if (!isCurrent()) return;
      const context = () =>
        JSON.stringify([
          useCurrentMarketStore().symbol_id,
          useCurrentTimeframeStore().value,
          overlay.selectedRunId,
        ]);
      const originalContext = context();
      const canSelect = () => isCurrent() && context() === originalContext;
      if (overlay.selectedRun?.run_id !== runId) {
        const { getBacktestRun } = await import('@/api/backtesterClient');
        if (!canSelect()) return;
        const run = await getBacktestRun(runId);
        if (!canSelect()) return;
        const selection = await overlay.selectRun(run, canSelect);
        if (!selection.selectable || !isCurrent()) return;
      } else overlay.restoreChartView();
      if (!overlay.matchesChart || !isCurrent()) return;
      navigating = true;
      await router.push('/');
      if (
        !isCurrent() ||
        !overlay.matchesChart ||
        router.currentRoute.value.path !== '/'
      )
        return;
      destination.value = { id, runId, timestampMs };
    } catch (error) {
      if (isCurrent()) console.error('Could not open trade on chart:', error);
    } finally {
      removeGuard();
      if (isCurrent()) preparing.value = false;
    }
  }
  return { destination, revision, loading, preparing, open, cancel };
});
