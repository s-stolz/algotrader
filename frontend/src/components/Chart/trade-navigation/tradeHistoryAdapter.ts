import { fetchCandles } from '@/api/candleClient';
import { extendIndicatorHistory } from '@/stores/indicators/forwardHistory';
import type { ChartCandle } from '@/types/contracts';
import type { useCandlesticksStore } from '@/stores/candlesticksStore';
import type { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { ChartInfrastructure } from '@/utils/chart';
import type { ChartSessionKey } from '../chartSession';
import type { TradeHistoryAdapter } from './tradeHistory';

interface Options {
  candles: ReturnType<typeof useCandlesticksStore>;
  indicators: ReturnType<typeof useIndicatorsStore>;
  infrastructure: ChartInfrastructure;
  render: (candles: readonly ChartCandle[]) => void;
  reset: () => void;
  initializeIndicators: (key: ChartSessionKey) => Promise<void>;
  loading: (value: boolean) => void;
}

export function createTradeHistoryAdapter(
  options: Options,
): TradeHistoryAdapter {
  const { candles, indicators, infrastructure } = options;
  const timeScale = () => infrastructure.chartManager.chart?.timeScale();
  let width = 50;
  return {
    getRange() {
      const range = timeScale()?.getVisibleLogicalRange();
      const series = infrastructure.getSeries().get('ohlc')?.series;
      const bars = range && series?.barsInLogicalRange(range);
      return bars
        ? {
            barsBefore: bars.barsBefore,
            barsAfter: bars.barsAfter,
            nowMs: performance.now(),
          }
        : null;
    },
    historical(value) {
      indicators.historicalMode = value;
      if (value) void indicators.unsubscribeAllLive();
      timeScale()?.applyOptions({ shiftVisibleRangeOnNewBar: !value });
    },
    resumeLive(key) {
      for (const indicator of indicators.all)
        void indicators.subscribeIndicatorLive(indicator._id, {
          ...key,
          indicatorId: indicator.indicatorId,
          parameters: indicators.extractParameterValues(indicator.parameters),
        });
    },
    prepare() {
      const range = timeScale()?.getVisibleLogicalRange();
      if (range) width = range.to - range.from;
      options.reset();
      indicators.resetHistoryFlags();
      for (const indicator of indicators.all)
        indicators.updateIndicatorData(indicator._id, []);
      candles.clear();
      options.render([]);
    },
    async fetchBefore(key, endMs, limit, signal) {
      let before: ChartCandle[] = [];
      while (before.length < limit) {
        const batch = await fetchCandles(
          key.symbol,
          key.timeframe,
          { exchange: key.exchange, endMs, limit: limit - before.length },
          signal,
        );
        signal.throwIfAborted();
        if (!batch.length || batch[0].timestamp_ms >= endMs) break;
        before = [...batch, ...before];
        endMs = batch[0].timestamp_ms;
      }
      return before;
    },
    fetchAfter: (key, startMs, signal) => {
      if (startMs >= Date.now()) return Promise.resolve([]);
      return fetchCandles(
        key.symbol,
        key.timeframe,
        {
          exchange: key.exchange,
          startMs,
          endMs: Date.now(),
          limit: 500,
          fromStart: true,
        },
        signal,
      );
    },
    install(incoming, targetMs) {
      const merged = new Map(
        candles.data.map((candle) => [candle.timestamp_ms, candle]),
      );
      for (const candle of incoming) merged.set(candle.timestamp_ms, candle);
      candles.replace(
        [...merged.values()].sort((a, b) => a.timestamp_ms - b.timestamp_ms),
      );
      options.render(candles.data);
      if (targetMs !== null) {
        let index = candles.data.length - 1;
        while (index > 0 && candles.data[index].timestamp_ms > targetMs)
          index -= 1;
        const from = Math.max(0, index - Math.min(10, Math.max(0, width - 1)));
        timeScale()?.setVisibleLogicalRange({ from, to: from + width });
      }
    },
    initializeIndicators: options.initializeIndicators,
    extendIndicators: (key, batch, signal) =>
      extendIndicatorHistory(indicators, key, batch, signal),
    loading: options.loading,
  };
}
