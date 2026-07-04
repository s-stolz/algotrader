import { defineStore } from 'pinia';
import { ref } from 'vue';

import { fetchBacktestClosedTrades, getBacktestRun } from '@/api/backtesterClient';
import {
  BACKTEST_RESULT_SCHEMA_VERSION,
  type BacktestClosedTrade,
  type BacktestRun,
} from '@/types/backtesterContracts';
import type { Market } from '@/types/contracts';
import { getStoredState, setStoredState, STORAGE_KEYS } from '@/utils/localStorage';
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

export function getBacktestRunSelectability(run: BacktestRun): BacktestRunSelectability {
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
  const symbol = run.request.symbols[0];
  const exchange = run.request.exchange;

  return markets.find((market) => {
    if (market.symbol !== symbol) {
      return false;
    }

    if (exchange) {
      return market.exchange === exchange;
    }

    return true;
  }) ?? null;
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
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  function clearSelectionData(): void {
    selectedRunId.value = null;
    selectedRun.value = null;
    closedTrades.value = [];
    localStorage.removeItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN);
  }

  function clearOverlay(): void {
    clearSelectionData();
    error.value = null;
  }

  function getSelectableBacktestRun(run: BacktestRun): BacktestRunSelectability {
    return getBacktestRunSelectabilityForMarkets(run, useMarketsStore().all);
  }

  async function selectRun(run: BacktestRun): Promise<BacktestRunSelectability> {
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
      const trades = await fetchBacktestClosedTrades(run.run_id);
      const timeframe = normalizeTimeframeCode(run.request.timeframe);

      useCurrentMarketStore().setMarket(market);
      useCurrentTimeframeStore().setCurrentTimeframe({
        label: timeframe,
        value: timeframe,
      });

      selectedRunId.value = run.run_id;
      selectedRun.value = run;
      closedTrades.value = trades;
      setStoredState(STORAGE_KEYS.SELECTED_BACKTEST_RUN, run.run_id);

      return selectability;
    } catch (err) {
      error.value = err instanceof Error
        ? err.message
        : 'Failed to select Backtest Run.';
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function restorePersistedSelection(): Promise<BacktestRunSelectability | null> {
    const runId = readStoredRunId();

    if (!runId) {
      return null;
    }

    isLoading.value = true;
    error.value = null;

    try {
      const run = await getBacktestRun(runId);
      const selectability = await selectRun(run);

      if (!selectability.selectable) {
        clearSelectionData();
      }

      return selectability;
    } catch (err) {
      clearOverlay();
      error.value = err instanceof Error
        ? err.message
        : 'Failed to reload selected Backtest Run.';
      return unavailable(error.value);
    } finally {
      isLoading.value = false;
    }
  }

  function getClosedTradesForRange(startMs: number, endMs: number): BacktestClosedTrade[] {
    return closedTrades.value.filter((trade) => (
      trade.exit_timestamp_ms >= startMs && trade.entry_timestamp_ms <= endMs
    ));
  }

  return {
    selectedRunId,
    selectedRun,
    closedTrades,
    isLoading,
    error,
    clearOverlay,
    getBacktestRunSelectability: getSelectableBacktestRun,
    getClosedTradesForRange,
    restorePersistedSelection,
    selectRun,
  };
});
