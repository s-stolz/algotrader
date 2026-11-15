import { createChartDrag } from './chartDrag';
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
  const drag = createChartDrag(() => infrastructure.chartManager.container);
  let generation = 0;
  let width = 50;
  let pendingRange: { from: number; to: number } | null = null;
  let rangeFrame: number | null = null;
  let rendering = false;
  let userInteraction: Event | null = null;
  const interactionEvents = ['wheel', 'mousemove', 'touchmove'];
  function markUserInteraction(event: Event) {
    userInteraction = event;
  }
  let observedRange: { from: number; to: number } | null = null;
  let stopWatchingRange: (() => void) | null = null;
  function clearPendingRange() {
    if (rangeFrame !== null) cancelAnimationFrame(rangeFrame);
    stopWatchingRange?.();
    stopWatchingRange = null;
    pendingRange = null;
    observedRange = null;
    rangeFrame = null;
  }
  function watchUserRange(range: { from: number; to: number } | null) {
    // Rebase gestures onto the requested viewport: setData can temporarily
    // clamp the internal range before the queued restoration is painted.
    const previous = observedRange;
    observedRange = range;
    if (
      userInteraction &&
      userInteraction.eventPhase !== Event.NONE &&
      !rendering &&
      pendingRange &&
      previous &&
      range &&
      (range.from !== pendingRange.from || range.to !== pendingRange.to)
    ) {
      restoreRange({
        from: pendingRange.from + range.from - previous.from,
        to: pendingRange.to + range.to - previous.to,
      });
    }
  }
  function restoreRange(range: { from: number; to: number }) {
    // The chart applies ranges on its next frame. Fast batches must preserve
    // that pending destination instead of reading the previous viewport.
    pendingRange = range;
    const scale = timeScale();
    observedRange = scale?.getVisibleLogicalRange() ?? null;
    if (scale && !stopWatchingRange) {
      scale.subscribeVisibleLogicalRangeChange(watchUserRange);
      for (const event of interactionEvents)
        window.addEventListener(event, markUserInteraction, true);
      stopWatchingRange = () => {
        scale.unsubscribeVisibleLogicalRangeChange(watchUserRange);
        for (const event of interactionEvents)
          window.removeEventListener(event, markUserInteraction, true);
        userInteraction = null;
      };
    }
    scale?.setVisibleLogicalRange(range);
    if (rangeFrame !== null) cancelAnimationFrame(rangeFrame);
    rangeFrame = requestAnimationFrame(clearPendingRange);
  }
  function append(
    incoming: readonly ChartCandle[],
    targetMs: number | null,
  ): void | Promise<void> {
    if (drag.active) {
      const current = generation;
      return drag.wait().then(() => {
        if (current === generation) return append(incoming, targetMs);
      });
    }
    const scale = timeScale();
    const range = pendingRange ?? scale?.getVisibleLogicalRange();
    candles.replace([...candles.data, ...incoming]);
    rendering = true;
    try {
      options.render(candles.data);
    } finally {
      rendering = false;
    }
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
      generation += 1;
      drag.begin();
      const range = pendingRange ?? timeScale()?.getVisibleLogicalRange();
      if (range) width = range.to - range.from;
      clearPendingRange();
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
    waitForInteraction: drag.wait,
    finish(live) {
      drag.stop();
      const range = pendingRange ?? timeScale()?.getVisibleLogicalRange();
      const merged = new Map(
        candles.data.map((candle) => [candle.timestamp_ms, candle]),
      );
      for (const candle of live)
        merged.set(candle.timestamp_ms, toChartCandle(candle));
      candles.replace(
        [...merged.values()].sort((a, b) => a.timestamp_ms - b.timestamp_ms),
      );
      rendering = true;
      try {
        options.render(candles.data);
        indicators.forwardHistory.finish(indicators);
      } finally {
        rendering = false;
      }
      if (range) restoreRange(range);
    },
    cancel: (hold) => {
      generation += 1;
      drag.stop();
      clearPendingRange();
      indicators.forwardHistory.discard(hold);
    },
    loading: options.loading,
  };
}
