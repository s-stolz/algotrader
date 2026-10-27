import { shallowReactive } from 'vue';
import type {
  CandlestickSeriesPartialOptions,
  MouseEventParams,
  Point,
  Time,
} from 'lightweight-charts';
import type {
  CandleUpdateMessage,
  ChartCandle,
  IndicatorUpdateMessage,
} from '@/types/contracts';
import {
  wsService,
  type WebSocketEventHandler,
} from '@/utils/websocketService';
import type {
  ChartInfrastructure,
  ChartLogicalRange,
  ManagedSeriesApi,
} from '@/utils/chart';
import {
  buildBacktestProtectiveLineSegments,
  buildBacktestTradeMarkers,
  formatBacktestMarkerDetails,
  type LoadedCandleRange,
} from '@/utils/chart/backtestOverlay';
import { getOrCreatePaneOverlayWrapper } from '@/utils/chart/paneOverlay';
import type { useCandlesticksStore } from '@/stores/candlesticksStore';
import type { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import type { ChartSession } from './chartSession';
import type { createChartMeasurement } from './chartMeasurement';

const WHEEL_SETTLE_MS = 250;
interface OhlcLegendPoint {
  open?: number;
  high?: number;
  low?: number;
  close?: number;
}
interface RenderCandlestickOptions {
  scrollToRealtime?: boolean;
}
interface ChartRenderingState {
  seriesOptions: CandlestickSeriesPartialOptions;
  crosshairRafId: number | null;
  latestCrosshairParam: MouseEventParams<Time> | null;
  visibleRangeRafId: number | null;
  latestVisibleRange: ChartLogicalRange | null;
  indicatorFlushRafId: number | null;
  pendingIndicatorMessages: Map<string, IndicatorUpdateMessage>;
  ohlcSeriesRef: ManagedSeriesApi | null;
  lastWheelTs: number;
  wheelSettleTimer: ReturnType<typeof setTimeout> | null;
  shouldScrollToRealTime: boolean;
  indicatorMessageHandler: WebSocketEventHandler<'indicatorUpdate'> | null;
  backtestOverlayTarget: HTMLElement | null;
  backtestMarkerDetails: Map<string, string>;
  hoveredBacktestMarker: string | null;
}
interface ChartRenderingOptions {
  infrastructure: ChartInfrastructure;
  candlesticksStore: ReturnType<typeof useCandlesticksStore>;
  indicatorsStore: ReturnType<typeof useIndicatorsStore>;
  backtestOverlayStore: ReturnType<typeof useBacktestOverlayStore>;
  measurement: ReturnType<typeof createChartMeasurement>;
  getChartContainer: () => HTMLElement | null;
  getMinMove: () => number | null;
  getLegendElements: () => Record<string, unknown>;
  requestOlderHistory: ChartSession['requestOlderHistory'];
}
function isOhlcLegendPoint(value: unknown): value is OhlcLegendPoint {
  return (
    typeof value === 'object' &&
    value !== null &&
    ('open' in value || 'high' in value || 'low' in value || 'close' in value)
  );
}

export function createChartRendering({
  infrastructure,
  candlesticksStore,
  indicatorsStore,
  backtestOverlayStore,
  measurement,
  getChartContainer,
  getMinMove,
  getLegendElements,
  requestOlderHistory,
}: ChartRenderingOptions) {
  const state = shallowReactive<ChartRenderingState>({
    seriesOptions: { priceFormat: { type: 'price' } },
    crosshairRafId: null,
    latestCrosshairParam: null,
    visibleRangeRafId: null,
    latestVisibleRange: null,
    indicatorFlushRafId: null,
    pendingIndicatorMessages: new Map(),
    ohlcSeriesRef: null,
    lastWheelTs: 0,
    wheelSettleTimer: null,
    shouldScrollToRealTime: false,
    indicatorMessageHandler: null,
    backtestOverlayTarget: null,
    backtestMarkerDetails: new Map(),
    hoveredBacktestMarker: null,
  });
  function initializeChartComponent(): void {
    infrastructure.init(getChartContainer());
    void syncBacktestOverlayTarget();
    infrastructure.subscribeCrosshairMove(onCrosshairMove);
    infrastructure.subscribeVisibleLogicalRangeChange(
      onVisibleLogicalRangeChange,
    );
    const chartContainer = getChartContainer();
    if (chartContainer) {
      chartContainer.addEventListener('wheel', onWheelPassive, {
        passive: true,
      });
    }
    measurement.applyInteractionMode();
    state.indicatorMessageHandler = (message) => {
      if (!message?.clientIndicatorId) return;
      state.pendingIndicatorMessages.set(message.clientIndicatorId, message);
      scheduleIndicatorFlush();
    };
    wsService.on('indicatorUpdate', state.indicatorMessageHandler);
  }

  async function syncBacktestOverlayTarget(): Promise<void> {
    const paneHtmlElement =
      await infrastructure.chartManager.getPaneHtmlElement(0);
    measurement.setMeasurementPaneElement(paneHtmlElement);
    state.backtestOverlayTarget = paneHtmlElement
      ? getOrCreatePaneOverlayWrapper(paneHtmlElement)
      : null;
  }

  function onWheelPassive(): void {
    state.lastWheelTs = performance.now();
    if (state.wheelSettleTimer !== null) {
      clearTimeout(state.wheelSettleTimer);
    }
    state.wheelSettleTimer = setTimeout(() => {
      state.wheelSettleTimer = null;
      if (state.latestVisibleRange) {
        onVisibleLogicalRangeChange(state.latestVisibleRange);
      }
    }, WHEEL_SETTLE_MS + 20);
  }

  function scheduleIndicatorFlush(): void {
    if (state.indicatorFlushRafId !== null) return;
    state.indicatorFlushRafId = requestAnimationFrame(() => {
      state.indicatorFlushRafId = null;
      flushIndicatorUpdates();
    });
  }

  function flushIndicatorUpdates(): void {
    if (state.pendingIndicatorMessages.size === 0) return;

    for (const [
      indicatorId,
      message,
    ] of state.pendingIndicatorMessages.entries()) {
      const point = indicatorsStore.handleLiveUpdate(message);
      if (!point) continue;
      infrastructure.indicatorManager.updateIndicatorSeriesPoint(
        indicatorId,
        point,
      );
    }
    state.pendingIndicatorMessages.clear();
  }

  function renderCandlesticks(
    data: readonly ChartCandle[],
    { scrollToRealtime = false }: RenderCandlestickOptions = {},
  ): void {
    const minMove = getMinMove();
    if (minMove && minMove > 0) {
      state.seriesOptions.priceFormat = {
        type: 'price',
        minMove,
        precision: Math.log10(1 / minMove),
      };
    }

    state.ohlcSeriesRef = infrastructure.addCandlestickData(
      data,
      state.seriesOptions,
    );
    void syncBacktestOverlayTarget();
    refreshBacktestMarkers();

    if (scrollToRealtime) {
      infrastructure.scrollToRealTime();
      setTimeout(() => {
        state.shouldScrollToRealTime = false;
      }, 100);
    }
  }

  function updateCurrentCandle(candle: CandleUpdateMessage): void {
    candlesticksStore.updateCandle(candle);
    infrastructure.updateCandlestick({
      timestamp_ms: candle.timestamp_ms,
      time: Math.floor(candle.timestamp_ms / 1000),
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
      volume: candle.volume,
    });
    refreshBacktestMarkers();
  }

  function getBacktestLoadedCandleRange(): LoadedCandleRange | null {
    if (candlesticksStore.data.length === 0) {
      return null;
    }

    let startMs = Number.POSITIVE_INFINITY;
    let endMs = Number.NEGATIVE_INFINITY;

    for (const candle of candlesticksStore.data) {
      startMs = Math.min(startMs, candle.timestamp_ms);
      endMs = Math.max(endMs, candle.timestamp_ms);
    }

    return { startMs, endMs };
  }

  function refreshBacktestMarkers(): void {
    state.hoveredBacktestMarker = null;
    state.backtestMarkerDetails.clear();
    const range = getBacktestLoadedCandleRange();

    if (!backtestOverlayStore.selectedRun || !range) {
      infrastructure.setCandlestickMarkers([]);
      infrastructure.setCandlestickProtectiveLines([]);
      return;
    }

    const trades = backtestOverlayStore.getClosedTradesForRange(
      range.startMs,
      range.endMs,
    );
    for (const trade of trades) {
      for (const kind of ['entry', 'exit'] as const) {
        state.backtestMarkerDetails.set(
          `${trade.trade_id}:${kind}`,
          formatBacktestMarkerDetails(trade, kind, getMinMove()),
        );
      }
    }
    infrastructure.setCandlestickMarkers(
      buildBacktestTradeMarkers(trades, range, getMinMove()),
    );
    infrastructure.setCandlestickProtectiveLines(
      buildBacktestProtectiveLineSegments(trades),
    );
  }

  function removeBacktestOverlay(): void {
    backtestOverlayStore.clearOverlay();
    refreshBacktestMarkers();
  }

  function onCrosshairMove(param: MouseEventParams<Time>): void {
    try {
      const validCrosshairPoint = isValidCrosshairPoint(param);
      state.hoveredBacktestMarker =
        validCrosshairPoint &&
        (param.paneIndex === undefined || param.paneIndex === 0) &&
        typeof param.hoveredObjectId === 'string'
          ? (state.backtestMarkerDetails.get(param.hoveredObjectId) ?? null)
          : null;
      if (!validCrosshairPoint) {
        return;
      }

      state.latestCrosshairParam = param;
      if (state.crosshairRafId !== null) return;

      state.crosshairRafId = requestAnimationFrame(() => {
        state.crosshairRafId = null;
        const current = state.latestCrosshairParam;
        if (!current) return;

        const bar = state.ohlcSeriesRef
          ? current.seriesData.get(state.ohlcSeriesRef)
          : null;
        if (!isOhlcLegendPoint(bar)) return;

        updateLegend(bar);
      });
    } catch (error) {
      console.log('Error in crosshair move handler:', error);
    }
  }

  function updateLegend(bar: OhlcLegendPoint): void {
    const elements = getLegendElements();
    if (elements.legendOpen instanceof HTMLElement) {
      elements.legendOpen.textContent = String(bar.open ?? '-');
    }
    if (elements.legendHigh instanceof HTMLElement) {
      elements.legendHigh.textContent = String(bar.high ?? '-');
    }
    if (elements.legendLow instanceof HTMLElement) {
      elements.legendLow.textContent = String(bar.low ?? '-');
    }
    if (elements.legendClose instanceof HTMLElement) {
      elements.legendClose.textContent = String(bar.close ?? '-');
    }
  }

  function onVisibleLogicalRangeChange(
    newVisibleLogicalRange: ChartLogicalRange | null,
  ): void {
    state.latestVisibleRange = newVisibleLogicalRange;
    if (state.visibleRangeRafId !== null) return;

    state.visibleRangeRafId = requestAnimationFrame(() => {
      state.visibleRangeRafId = null;
      const range = state.latestVisibleRange;
      if (!range) return;

      const ohlc = infrastructure.getSeries().get('ohlc');
      if (!ohlc) return;

      const barsInfo = ohlc.series.barsInLogicalRange(range);
      if (barsInfo === null) return;
      const now = performance.now();
      if (now - state.lastWheelTs < WHEEL_SETTLE_MS) {
        return;
      }

      requestOlderHistory({
        barsBefore: barsInfo.barsBefore,
        nowMs: now,
        scrollToRealtime: state.shouldScrollToRealTime,
      });
    });
  }

  function isValidCrosshairPoint(
    param: MouseEventParams<Time> | undefined,
  ): param is MouseEventParams<Time> & { time: Time; point: Point } {
    return (
      param !== undefined &&
      param.time !== undefined &&
      param.point !== undefined &&
      param.point.x >= 0 &&
      param.point.y >= 0
    );
  }

  function dispose() {
    for (const id of [
      state.crosshairRafId,
      state.visibleRangeRafId,
      state.indicatorFlushRafId,
    ]) {
      if (id !== null) cancelAnimationFrame(id);
    }
    state.crosshairRafId =
      state.visibleRangeRafId =
      state.indicatorFlushRafId =
        null;
    state.pendingIndicatorMessages.clear();
    if (state.indicatorMessageHandler) {
      wsService.off('indicatorUpdate', state.indicatorMessageHandler);
      state.indicatorMessageHandler = null;
    }
    if (state.wheelSettleTimer !== null) clearTimeout(state.wheelSettleTimer);
    state.wheelSettleTimer = null;
    measurement.dispose();
    getChartContainer()?.removeEventListener('wheel', onWheelPassive);
  }
  return {
    state,
    initializeChartComponent,
    renderCandlesticks,
    updateCurrentCandle,
    refreshBacktestMarkers,
    removeBacktestOverlay,
    onWheelPassive,
    dispose,
  };
}
