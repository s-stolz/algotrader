import { HttpResponseError } from '@/api/http';
import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

import {
  fetchBacktestClosedTrades,
  fetchBacktestFills,
  getBacktestRun,
} from '@/api/backtesterClient';
import {
  BACKTEST_RESULT_SCHEMA_VERSION,
  type BacktestClosedTrade,
  type BacktestFill,
  type BacktestRun,
} from '@/types/backtesterContracts';
import type { Market } from '@/types/contracts';
import {
  getStoredState,
  setStoredState,
  STORAGE_KEYS,
} from '@/utils/localStorage';
import { matchesBacktestMarket } from '@/utils/backtestMarket';
import { normalizeTimeframeCode } from '@/utils/timeframes';

import { useCurrentMarketStore } from './currentMarketStore';
import { useCurrentTimeframeStore } from './currentTimeframeStore';
import { useMarketsStore } from './marketsStore';

export interface BacktestRunSelectability {
  selectable: boolean;
  reason: string | null;
}

const SELECTABLE: BacktestRunSelectability = {
  selectable: true,
  reason: null,
};

function readStoredRunId(): string | null {
  const stored = getStoredState<unknown>(STORAGE_KEYS.SELECTED_BACKTEST_RUN);

  if (typeof stored === 'string' && stored.length > 0) {
    return stored;
  }

  return null;
}

function unavailable(reason: string): BacktestRunSelectability {
  return {
    selectable: false,
    reason,
  };
}

export function getBacktestRunSelectability(
  run: BacktestRun,
): BacktestRunSelectability {
  if (run.status !== 'succeeded') {
    return unavailable('Only succeeded Backtest Runs can be opened.');
  }

  if (run.result_schema_version !== BACKTEST_RESULT_SCHEMA_VERSION) {
    return unavailable('Backtest Run result schema is unsupported.');
  }

  if (run.request.symbols.length === 0) {
    return unavailable('Backtest Run has no symbol.');
  }

  if (run.request.symbols.length > 1) {
    return unavailable('Backtest Run has multiple symbols.');
  }

  return SELECTABLE;
}

function findMarketForRun(run: BacktestRun, markets: Market[]): Market | null {
  return (
    markets.find((market) =>
      matchesBacktestMarket(market, run.request, 'allow-unspecified'),
    ) ?? null
  );
}

function formatMarketMissingReason(run: BacktestRun): string {
  const symbol = run.request.symbols[0] ?? 'unknown symbol';
  const exchange = run.request.exchange;

  if (exchange) {
    return `Market ${exchange}:${symbol} is not available in the chart market list.`;
  }

  return `Market ${symbol} is not available in the chart market list.`;
}

function getBacktestRunSelectabilityForMarkets(
  run: BacktestRun,
  markets: Market[],
): BacktestRunSelectability {
  const selectability = getBacktestRunSelectability(run);

  if (!selectability.selectable) {
    return selectability;
  }

  if (!findMarketForRun(run, markets)) {
    return unavailable(formatMarketMissingReason(run));
  }

  return selectability;
}

export const useBacktestOverlayStore = defineStore('backtestOverlay', () => {
  const selectedRunId = ref<string | null>(readStoredRunId());
  const selectedRun = ref<BacktestRun | null>(null);
  const closedTrades = ref<BacktestClosedTrade[]>([]);
  const fills = ref<BacktestFill[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  let selectionRevision = 0;
  const matchesChart = computed(() => {
    const run = selectedRun.value;
    const market = useCurrentMarketStore();
    return (
      !!run &&
      (matchesBacktestMarket(market, run.request, 'allow-unspecified') ||
        findMarketForRun(run, useMarketsStore().all)?.symbol_id ===
          market.symbol_id) &&
      normalizeTimeframeCode(run.request.timeframe) ===
        useCurrentTimeframeStore().value
    );
  });

  function restoreChartView(): void {
    const run = selectedRun.value;
    if (!run) return;
    const market = findMarketForRun(run, useMarketsStore().all);
    if (!market) {
      error.value = formatMarketMissingReason(run);
      return;
    }
    useCurrentMarketStore().setMarket(market);
    const timeframe = normalizeTimeframeCode(run.request.timeframe);
    useCurrentTimeframeStore().setCurrentTimeframe({
      label: timeframe,
      value: timeframe,
    });
  }

  function clearSelectionData(): void {
    selectionRevision += 1;
    isLoading.value = false;
    selectedRunId.value = null;
    selectedRun.value = null;
    closedTrades.value = [];
    fills.value = [];
    localStorage.removeItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN);
  }

  function clearOverlay(): void {
    clearSelectionData();
    error.value = null;
  }

  function getSelectableBacktestRun(
    run: BacktestRun,
  ): BacktestRunSelectability {
    return getBacktestRunSelectabilityForMarkets(run, useMarketsStore().all);
  }

  async function selectRun(
    run: BacktestRun,
    isCurrent: () => boolean = () => true,
  ): Promise<BacktestRunSelectability> {
    const revision = ++selectionRevision;
    isLoading.value = false;
    const markets = useMarketsStore().all;
    const selectability = getBacktestRunSelectabilityForMarkets(run, markets);

    if (!selectability.selectable) {
      error.value = selectability.reason;
      return selectability;
    }

    const market = findMarketForRun(run, markets);

    if (!market) {
      const reason = formatMarketMissingReason(run);
      error.value = reason;
      return unavailable(reason);
    }

    isLoading.value = true;
    error.value = null;

    try {
      const [trades, runFills] = await Promise.all([
        fetchBacktestClosedTrades(run.run_id),
        fetchBacktestFills(run.run_id),
      ]);
      if (revision !== selectionRevision || !isCurrent())
        return unavailable('Selection changed.');
      const timeframe = normalizeTimeframeCode(run.request.timeframe);

      useCurrentMarketStore().setMarket(market);
      useCurrentTimeframeStore().setCurrentTimeframe({
        label: timeframe,
        value: timeframe,
      });

      selectedRunId.value = run.run_id;
      selectedRun.value = run;
      fills.value = runFills;
      closedTrades.value = trades;
      setStoredState(STORAGE_KEYS.SELECTED_BACKTEST_RUN, run.run_id);

      return selectability;
    } catch (err) {
      if (revision !== selectionRevision || !isCurrent())
        return unavailable('Selection changed.');
      error.value =
        err instanceof Error ? err.message : 'Failed to select Backtest.';
      throw err;
    } finally {
      if (revision === selectionRevision) isLoading.value = false;
    }
  }

  async function restorePersistedSelection(): Promise<BacktestRunSelectability | null> {
    const revision = ++selectionRevision;
    const runId = readStoredRunId();
    if (!runId) return null;
    isLoading.value = true;
    error.value = null;
    try {
      const run = await getBacktestRun(runId);
      if (revision !== selectionRevision) return null;
      const selectability = getSelectableBacktestRun(run);
      if (!selectability.selectable) {
        console.error(
          'Cannot restore selected Backtest:',
          selectability.reason,
        );
        clearSelectionData();
        return selectability;
      }
      const [trades, runFills] = await Promise.all([
        fetchBacktestClosedTrades(runId),
        fetchBacktestFills(runId),
      ]);
      if (revision !== selectionRevision) return null;
      selectedRunId.value = runId;
      selectedRun.value = run;
      fills.value = runFills;
      closedTrades.value = trades;
      return selectability;
    } catch (err) {
      if (revision !== selectionRevision) return null;
      console.error('Failed to restore selected Backtest:', err);
      if (err instanceof HttpResponseError && [404, 410].includes(err.status)) {
        clearSelectionData();
      }
      return unavailable(
        err instanceof Error
          ? err.message
          : 'Failed to reload selected Backtest.',
      );
    } finally {
      if (revision === selectionRevision) isLoading.value = false;
    }
  }

  function getClosedTradesForRange(
    startMs: number,
    endMs: number,
  ): BacktestClosedTrade[] {
    return closedTrades.value.filter(
      (trade) =>
        trade.exit_timestamp_ms >= startMs && trade.entry_timestamp_ms <= endMs,
    );
  }

  return {
    matchesChart,
    restoreChartView,
    selectedRunId,
    selectedRun,
    closedTrades,
    fills,
    isLoading,
    error,
    clearOverlay,
    getBacktestRunSelectability: getSelectableBacktestRun,
    getClosedTradesForRange,
    restorePersistedSelection,
    selectRun,
  };
});
