import { fetchCandles } from '@/api/candleClient';
import { streamCandles } from '@/api/candleStream';
import { extendIndicatorHistory } from '@/stores/indicators/forwardHistory';
import { toChartCandle, type ChartCandle } from '@/types/contracts';
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
  let pendingRange: { from: number; to: number } | null = null;
  let rangeFrame: number | null = null;
  function restoreRange(range: { from: number; to: number }) {
    // The chart applies ranges on its next frame. Fast batches must preserve
    // that pending destination instead of reading the previous viewport.
    pendingRange = range;
    timeScale()?.setVisibleLogicalRange(range);
    if (rangeFrame !== null) cancelAnimationFrame(rangeFrame);
    rangeFrame = requestAnimationFrame(() => {
      pendingRange = null;
      rangeFrame = null;
    });
  }
  function append(incoming: readonly ChartCandle[], targetMs: number | null) {
    const scale = timeScale();
    const range = pendingRange ?? scale?.getVisibleLogicalRange();
    candles.replace([...candles.data, ...incoming]);
    options.render(candles.data);
    if (targetMs !== null) {
      let index = candles.data.length - 1;
      while (index > 0 && candles.data[index].timestamp_ms > targetMs)
        index -= 1;
      const margin = Math.min(10, Math.max(0, width - 1));
      const from = Math.max(0, index - margin);
      restoreRange({ from, to: from + width });
    } else if (range) restoreRange(range);
  }
  return {
    prepare() {
      const range = pendingRange ?? timeScale()?.getVisibleLogicalRange();
      if (range) width = range.to - range.from;
      options.reset();
      indicators.forwardHistory.begin();
      indicators.resetHistoryFlags();
      for (const indicator of indicators.all)
        indicators.updateIndicatorData(indicator._id, []);
      candles.clear();
      options.render([]);
    },
    async fetchBefore(key, timestampMs, signal) {
      let endMs = timestampMs + 1;
      let before: ChartCandle[] = [];
      while (before.length < 11) {
        const batch = await fetchCandles(
          key.symbol,
          key.timeframe,
          {
            exchange: key.exchange,
            endMs,
            limit: 11 - before.length,
          },
          signal,
        );
        signal.throwIfAborted();
        if (!batch.length || batch[0].timestamp_ms >= endMs) break;
        before = [...batch, ...before];
        endMs = batch[0].timestamp_ms;
      }
      return before;
    },
    stream: (key, startMs, endMs, signal, onBatch) =>
      streamCandles(key.symbol, key.timeframe, {
        startMs,
        endMs,
        exchange: key.exchange,
        signal,
        onBatch,
      }),
    append,
    initializeIndicators: options.initializeIndicators,
    extendIndicators: (key, batch, signal) =>
      extendIndicatorHistory(indicators, key, batch, signal),
    finish(live) {
      const range = pendingRange ?? timeScale()?.getVisibleLogicalRange();
      const merged = new Map(
        candles.data.map((candle) => [candle.timestamp_ms, candle]),
      );
      for (const candle of live)
        merged.set(candle.timestamp_ms, toChartCandle(candle));
      candles.replace(
        [...merged.values()].sort((a, b) => a.timestamp_ms - b.timestamp_ms),
      );
      options.render(candles.data);
      indicators.forwardHistory.finish(indicators);
      if (range) restoreRange(range);
    },
    cancel: (hold) => indicators.forwardHistory.discard(hold),
    loading: options.loading,
  };
}
