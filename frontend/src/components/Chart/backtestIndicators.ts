import {
  getStoredState,
  setStoredState,
  STORAGE_KEYS,
} from '@/utils/localStorage';
import { isRecord } from '@/types/contracts';
import { isIndicatorStyles } from '@/stores/indicators/persistence';
import { ref, watch } from 'vue';
import {
  fetchAvailableIndicators,
  requestIndicator,
} from '@/api/indicatorClient';
import type { BacktestRun } from '@/types/backtesterContracts';
import { readChartIndicators } from '@/types/backtest/chartIndicators';
import type {
  useIndicatorsStore,
  IndicatorLoadedCandleRange,
  IndicatorStyles,
} from '@/stores/indicatorsStore';
import type { IndicatorManager } from '@/utils/chart/IndicatorManager';
import type { ChartSessionKey } from './chartSession';

interface Options {
  store: ReturnType<typeof useIndicatorsStore>;
  manager: Pick<
    IndicatorManager,
    'removeIndicatorSeriesAndData' | 'updateMissingPaneHtmlElements'
  >;
  getRange: () => IndicatorLoadedCandleRange | null;
}

export function createBacktestIndicators({
  store,
  manager,
  getRange,
}: Options) {
  const error = ref<string | null>(null);
  const isLoading = ref(false);
  let revision = 0;
  let styleRunId: string | null = null;
  let styles: (IndicatorStyles | null)[] = [];
  let panes: (number | null)[] = [];
  let ids: string[] = [];
  let stopStyles: (() => void)[] = [];

  function persistStyles() {
    setStoredState(STORAGE_KEYS.RUN_INDICATOR_STYLES, {
      version: 1,
      runId: styleRunId,
      styles,
      panes,
    });
  }

  function restoreStyles(runId: string | null) {
    const saved = getStoredState<unknown>(STORAGE_KEYS.RUN_INDICATOR_STYLES);
    panes =
      isRecord(saved) && saved.runId === runId && Array.isArray(saved.panes)
        ? saved.panes.map((pane) =>
            typeof pane === 'number' && Number.isInteger(pane) && pane > 0
              ? pane
              : null,
          )
        : [];
    styles =
      isRecord(saved) &&
      saved.version === 1 &&
      saved.runId === runId &&
      Array.isArray(saved.styles)
        ? saved.styles.map((style) => (isIndicatorStyles(style) ? style : null))
        : [];
  }

  function clear() {
    for (const stop of stopStyles) stop();
    stopStyles = [];
    for (const id of [...ids].reverse())
      manager.removeIndicatorSeriesAndData(id);
    ids = [];
    void manager.updateMissingPaneHtmlElements();
  }

  function invalidate(runId: string | null) {
    revision += 1;
    isLoading.value = false;
    error.value = null;
    if (ids.length) clear();
    if (runId !== styleRunId) {
      restoreStyles(runId);
      styleRunId = runId;
      persistStyles();
    }
  }

  async function load(
    run: Pick<BacktestRun, 'run_id' | 'diagnostics'>,
    key: ChartSessionKey,
  ) {
    const current = ++revision;
    isLoading.value = true;
    error.value = null;
    try {
      const saved = readChartIndicators(run.diagnostics);
      if (!saved?.length) return;
      const range = getRange();
      if (!range) return;
      const catalog = await fetchAvailableIndicators();
      if (current !== revision) return;
      const responses = await Promise.allSettled(
        saved.map(async (item) => {
          const match = catalog.find(
            (entry) => entry.indicator_id === item.indicator_id,
          );
          if (!match)
            throw new Error(`Indicator ${item.indicator_id} is unavailable.`);
          const response = await requestIndicator(
            match.id,
            {
              symbol: key.symbol,
              exchange: key.exchange ?? undefined,
              timeframe: key.timeframe,
              endMs: range.exclusiveEndMs,
              limit: 500,
            },
            { parameters: item.parameters },
          );
          if (response.data.indicator_info.indicator_id !== item.indicator_id) {
            throw new Error(
              'Indicator response does not match the saved configuration.',
            );
          }
          return response.data;
        }),
      );
      if (current !== revision) return;
      responses.forEach((result, index) => {
        if (result.status === 'rejected') {
          console.error('Failed to restore backtest indicator:', result.reason);
          return;
        }
        const response = result.value;
        const id = store.addIndicator(
          response.indicator_info,
          response.indicator_data,
          response.indicator_info.id,
          saved[index].parameters,
          run.run_id,
        );
        ids.push(id);
        const indicator = store.getById(id)!;
        if (styles[index]) indicator.styles = styles[index];
        const pane = panes[index];
        if (
          !indicator.info.overlay &&
          pane &&
          !store.all.some((item) => item._id !== id && item.paneIndex === pane)
        ) {
          indicator.paneIndex = pane;
          store.paneCount = Math.max(
            1,
            ...store.all.map((item) => item.paneIndex + 1),
          );
        }
        panes[index] = indicator.paneIndex || null;
        persistStyles();
        stopStyles.push(
          watch(
            () => [indicator.styles, indicator.paneIndex] as const,
            ([style, paneIndex]) => {
              styles[index] = style;
              panes[index] = paneIndex || null;
              persistStyles();
            },
            { deep: true, flush: 'sync' },
          ),
        );
        void store.subscribeIndicatorLive(id, {
          ...key,
          indicatorId: indicator.indicatorId,
          parameters: saved[index].parameters,
        });
      });
      await store.ensureCoverageForAll(key.symbol, key.timeframe, key.exchange);
    } catch (reason) {
      if (current === revision) {
        clear();
        console.error('Could not load backtest indicators:', reason);
      }
    } finally {
      if (current === revision) isLoading.value = false;
    }
  }

  return {
    error,
    isLoading,
    invalidate,
    load,
    dispose: () => {
      revision += 1;
      clear();
    },
  };
}
