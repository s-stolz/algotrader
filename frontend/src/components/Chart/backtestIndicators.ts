import { ref } from 'vue';
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
  let styles: IndicatorStyles[] = [];
  let ids: string[] = [];

  function clear() {
    styles = ids.map((id, index) => store.getById(id)?.styles ?? styles[index]);
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
    if (runId !== styleRunId) styles = [];
    styleRunId = runId;
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
      const responses = await Promise.all(
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
      responses.forEach((response, index) => {
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
        error.value =
          reason instanceof Error
            ? reason.message
            : 'Could not load backtest indicators.';
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
    dispose: () => invalidate(null),
  };
}
