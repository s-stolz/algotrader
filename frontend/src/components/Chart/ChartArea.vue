<template>
  <div id="chart-wrapper">
    <div
      ref="chartContainer"
      id="lightweight-chart"
      class="chart-container"
      :class="{ 'chart-container--measure-mode': interactionMode === 'measure' }"
    />

    <Teleport
      v-if="backtestOverlayStore.selectedRun && backtestOverlayTarget"
      :to="backtestOverlayTarget"
    >
      <div class="backtest-overlay-container">
        <div
          class="backtest-overlay-panel"
        >
          <div class="backtest-overlay-details">
            <span class="backtest-overlay-title">{{ activeBacktestRunTitle }}</span>
            <span class="backtest-overlay-context">{{ activeBacktestRunContext }}</span>
          </div>
          <n-button
            text
            class="backtest-overlay-remove"
            data-testid="remove-backtest-overlay"
            aria-label="Remove Backtest Run overlay"
            @click="removeBacktestOverlay"
          >
            <n-icon size="20">
              <CloseCircleOutline />
            </n-icon>
          </n-button>
        </div>
      </div>
    </Teleport>

    <span class="legend">
      <span class="legend-value">O: <span ref="legendOpen">-</span></span>
      <span class="legend-value">H: <span ref="legendHigh">-</span></span>
      <span class="legend-value">L: <span ref="legendLow">-</span></span>
      <span class="legend-value">C: <span ref="legendClose">-</span></span>
    </span>

    <div>
      <indicator
        v-for="indicator in getAllIndicators()"
        :key="indicator._id"
        :indicator="indicator"
        :indicator-manager="indicatorManager"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { markRaw, defineComponent, type PropType } from "vue";
import type {
  CandlestickSeriesPartialOptions,
  MouseEventParams,
  Point,
  Time,
} from "lightweight-charts";
import { NButton, NIcon } from "naive-ui";

import { useCandlesticksStore } from "@/stores/candlesticksStore";
import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
import { useBacktestOverlayStore } from "@/stores/backtestOverlayStore";
import { fetchCandles as fetchHistoricalCandles } from "@/api/candleClient";
import type {
  CandleUpdateMessage,
  ChartCandle,
  IndicatorUpdateMessage,
} from "@/types/contracts";
import { wsService, type WebSocketEventHandler } from "@/utils/websocketService";
import {
  createChartSession,
  type ChartSession,
  type ChartSessionKey,
  type ChartSessionSubscriptionsAdapter,
  type ChartSessionKeyInput,
} from "@/components/Chart/chartSession";
import {
  DEFAULT_CHART_INTERACTION_MODE,
  type ChartInteractionMode,
} from "@/components/Chart/chartInteractionMode";

import {
  createChartInfrastructure,
  type ChartInfrastructure,
  type ChartLogicalRange,
  type ChartOhlcPoint,
  type ManagedSeriesApi,
} from "@/utils/chart";
import { buildMeasurementOverlayModel } from "@/utils/chart/measurementOverlay";
import {
  buildBacktestProtectiveLineSegments,
  buildBacktestTradeMarkers,
  type LoadedCandleRange,
} from "@/utils/chart/backtestOverlay";
import { getOrCreatePaneOverlayWrapper } from "@/utils/chart/paneOverlay";
import { timeframeToMinutes } from "@/utils/timeframes";
import Indicator from "@/components/Chart/Indicator/Indicator.vue";
import { CloseCircleOutline } from "@/icons";

const WHEEL_SETTLE_MS = 250;

type CandlesticksStore = ReturnType<typeof useCandlesticksStore>;
type IndicatorsStore = ReturnType<typeof useIndicatorsStore>;
type CurrentMarketStore = ReturnType<typeof useCurrentMarketStore>;
type CurrentTimeframeStore = ReturnType<typeof useCurrentTimeframeStore>;
type BacktestOverlayStore = ReturnType<typeof useBacktestOverlayStore>;

interface OhlcLegendPoint {
  open?: number;
  high?: number;
  low?: number;
  close?: number;
}

interface RenderCandlestickOptions {
  scrollToRealtime?: boolean;
}

interface MeasurementEndpoint {
  price: number;
  logical: number;
}

interface MeasurementDragState {
  anchorPrice: number;
  anchorLogical: number;
  minMove: number;
}

interface ChartAreaData {
  candlesticksStore: CandlesticksStore;
  indicatorsStore: IndicatorsStore;
  currentMarketStore: CurrentMarketStore;
  currentTimeframeStore: CurrentTimeframeStore;
  backtestOverlayStore: BacktestOverlayStore;
  chartInfrastructure: ChartInfrastructure;
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
  candlesFetchLimit: number;
  indicatorBatchSize: number;
  shouldScrollToRealTime: boolean;
  indicatorMessageHandler: WebSocketEventHandler<"indicatorUpdate"> | null;
  chartSession: ChartSession | null;
  backtestOverlayTarget: HTMLElement | null;
  measurementPaneElement: HTMLElement | null;
  activeMeasurement: MeasurementDragState | null;
}

function isOhlcLegendPoint(value: unknown): value is OhlcLegendPoint {
  return (
    typeof value === "object" &&
    value !== null &&
    ("open" in value || "high" in value || "low" in value || "close" in value)
  );
}

export default defineComponent({
  name: "ChartArea",

  components: {
    CloseCircleOutline,
    Indicator,
    NButton,
    NIcon,
  },

  props: {
    interactionMode: {
      type: String as PropType<ChartInteractionMode>,
      default: DEFAULT_CHART_INTERACTION_MODE,
    },
  },

  data(): ChartAreaData {
    return {
      candlesticksStore: useCandlesticksStore(),
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      backtestOverlayStore: useBacktestOverlayStore(),
      chartInfrastructure: markRaw(createChartInfrastructure()),
      seriesOptions: {
        priceFormat: {
          type: "price",
        },
      },
      crosshairRafId: null,
      latestCrosshairParam: null,
      visibleRangeRafId: null,
      latestVisibleRange: null,
      indicatorFlushRafId: null,
      pendingIndicatorMessages: new Map(),
      ohlcSeriesRef: null,
      lastWheelTs: 0,
      wheelSettleTimer: null,
      candlesFetchLimit: 500,
      indicatorBatchSize: 500,
      shouldScrollToRealTime: false,
      indicatorMessageHandler: null,
      chartSession: null,
      backtestOverlayTarget: null,
      measurementPaneElement: null,
      activeMeasurement: null,
    };
  },

  computed: {
    indicatorManager() {
      return this.chartInfrastructure.indicatorManager;
    },

    currentMarketMinMove(): number | null {
      return this.currentMarketStore.min_move;
    },

    currentMarketKey(): string {
      const symbol = this.currentMarketStore.symbol || "";
      const exchange = this.currentMarketStore.exchange || "";
      return `${symbol}|${exchange}`;
    },

    activeBacktestRunTitle(): string {
      const run = this.backtestOverlayStore.selectedRun;
      if (!run) {
        return "";
      }

      return run.request.strategy.strategy_id;
    },

    activeBacktestRunContext(): string {
      const run = this.backtestOverlayStore.selectedRun;
      if (!run) {
        return "";
      }

      const symbol = run.request.symbols[0] ?? "unknown";
      const market = run.request.exchange ? `${run.request.exchange}:${symbol}` : symbol;

      return `${run.request.timeframe} ${market}`;
    },
  },

  watch: {
    currentMarketMinMove(newMinMove: number | null) {
      if (newMinMove && newMinMove > 0) {
        this.setMinMove(newMinMove);
      }
    },

    currentMarketKey: {
      handler(newKey: string, oldKey: string | undefined) {
        this.shouldScrollToRealTime = true;

        if (newKey !== oldKey) {
          this.syncChartSession();
        }
      },
      immediate: true,
    },

    "currentTimeframeStore.value": {
      handler(newTimeframe: string, oldTimeframe: string | undefined) {
        this.shouldScrollToRealTime = true;

        if (newTimeframe !== oldTimeframe) {
          this.syncChartSession();
        }
      },
      immediate: true,
    },

    "backtestOverlayStore.selectedRunId"() {
      this.refreshBacktestMarkers();
    },

    "backtestOverlayStore.closedTrades"() {
      this.refreshBacktestMarkers();
    },

    interactionMode() {
      this.applyInteractionMode();
    },
  },

  created(): void {
    this.chartSession = markRaw(createChartSession(this.createChartSessionAdapter()));
    this.syncChartSession();
  },

  mounted(): void {
    this.initializeChartComponent();
  },

  beforeUnmount(): void {
    void this.chartSession?.stop();
    if (this.crosshairRafId !== null) {
      cancelAnimationFrame(this.crosshairRafId);
      this.crosshairRafId = null;
    }
    if (this.visibleRangeRafId !== null) {
      cancelAnimationFrame(this.visibleRangeRafId);
      this.visibleRangeRafId = null;
    }
    if (this.indicatorFlushRafId !== null) {
      cancelAnimationFrame(this.indicatorFlushRafId);
      this.indicatorFlushRafId = null;
    }
    this.pendingIndicatorMessages.clear();
    if (this.indicatorMessageHandler) {
      wsService.off('indicatorUpdate', this.indicatorMessageHandler);
      this.indicatorMessageHandler = null;
    }
    if (this.wheelSettleTimer !== null) {
      clearTimeout(this.wheelSettleTimer);
      this.wheelSettleTimer = null;
    }
    this.cancelMeasurementOverlay();
    this.setMeasurementPaneElement(null);
    const chartContainer = this.getChartContainer();
    if (chartContainer) {
      chartContainer.removeEventListener("wheel", this.onWheelPassive);
    }
    this.indicatorsStore.configureHistoryCoverage(null);
    this.chartInfrastructure.cleanup();
  },

  methods: {
    createChartSessionAdapter(): ChartSessionSubscriptionsAdapter {
      this.indicatorsStore.configureHistoryCoverage({
        batchSize: this.indicatorBatchSize,
        getLoadedCandleRange: () => {
          const key = this.currentChartSessionKey();
          return key.timeframe ? this.getIndicatorLoadedCandleRange(key.timeframe) : null;
        },
      });

      const indicatorCoverageOptions = (key: ChartSessionKey) => ({
        batchSize: this.indicatorBatchSize,
        getLoadedCandleRange: () => this.getIndicatorLoadedCandleRange(key.timeframe),
      });

      return {
        subscribeCandles: (key) => wsService.send("subscribeCandles", {
          symbol: key.symbol,
          timeframe: key.timeframe,
        }),
        unsubscribeCandles: (key) => wsService.send("unsubscribeCandles", {
          symbol: key.symbol,
          timeframe: key.timeframe,
        }),
        onCandleUpdate: (handler) => {
          wsService.on("candleUpdate", handler);
        },
        offCandleUpdate: (handler) => {
          wsService.off("candleUpdate", handler);
        },
        fetchCandles: (key) => fetchHistoricalCandles(key.symbol, key.timeframe, {
          limit: this.candlesFetchLimit,
          exchange: key.exchange,
        }),
        renderCandles: (_key, candles) => {
          this.candlesticksStore.replace(candles);
          this.renderCandlesticks(this.candlesticksStore.data, {
            scrollToRealtime: this.shouldScrollToRealTime,
          });
        },
        requestIndicators: (key) => {
          this.indicatorsStore.requestAllIndicators(
            key.symbol,
            key.timeframe,
            key.exchange,
            indicatorCoverageOptions(key),
          );
        },
        unsubscribeIndicators: () => this.indicatorsStore.unsubscribeAllLive(),
        getOldestCandleTimestampMs: () => {
          return this.candlesticksStore.data[0]?.timestamp_ms ?? null;
        },
        fetchOlderCandles: (key, endMs) => fetchHistoricalCandles(key.symbol, key.timeframe, {
          endMs,
          limit: this.candlesFetchLimit,
          exchange: key.exchange,
        }),
        prependOlderCandles: (_key, candles) => {
          this.candlesticksStore.prepend(candles);
        },
        renderOlderCandles: (key) => {
          this.renderCandlesticks(this.candlesticksStore.data);
          void this.indicatorsStore.ensureCoverageForAll(
            key.symbol,
            key.timeframe,
            key.exchange,
            indicatorCoverageOptions(key),
          );
        },
        requestOlderIndicators: (key) => {
          return this.indicatorsStore.ensureCoverageForAll(
            key.symbol,
            key.timeframe,
            key.exchange,
            indicatorCoverageOptions(key),
          );
        },
        resetIndicatorHistory: () => {
          this.indicatorsStore.resetHistoryFlags();
        },
        reportCandleFetchError: (_key, error) => {
          console.error('Failed to fetch candlestick data:', error);
        },
        reportOlderCandleFetchError: (_key, error) => {
          console.error('Failed to fetch older candlestick data:', error);
        },
        reportOlderIndicatorFetchError: (_key, error) => {
          console.error('Failed to fetch older indicator data:', error);
        },
        reportLiveTailBufferOverflow: (key, candle) => {
          console.error('Live candle tail buffer overflow; refetching chart session.', {
            candle,
            key,
          });
        },
        reportSubscriptionError: (operation, _key, error) => {
          console.error(`Failed to ${operation} candle subscription:`, error);
        },
      };
    },

    initializeChartComponent(): void {
      this.chartInfrastructure.init(this.getChartContainer());
      void this.syncBacktestOverlayTarget();
      this.subscribeCrosshairMove(this.onCrosshairMove);
      this.subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChange);
      const chartContainer = this.getChartContainer();
      if (chartContainer) {
        chartContainer.addEventListener("wheel", this.onWheelPassive, { passive: true });
      }
      this.applyInteractionMode();
      this.indicatorMessageHandler = (message) => {
        if (!message?.clientIndicatorId) return;
        this.pendingIndicatorMessages.set(message.clientIndicatorId, message);
        this.scheduleIndicatorFlush();
      };
      wsService.on("indicatorUpdate", this.indicatorMessageHandler);
    },

    getChartContainer(): HTMLElement | null {
      const chartContainer = this.$refs.chartContainer;
      return chartContainer instanceof HTMLElement ? chartContainer : null;
    },

    setMeasurementPaneElement(paneElement: HTMLElement | null): void {
      if (this.measurementPaneElement === paneElement) {
        return;
      }

      if (this.measurementPaneElement) {
        this.measurementPaneElement.removeEventListener(
          "pointerdown",
          this.onMeasurementPointerDown,
          true,
        );
      }

      this.measurementPaneElement = paneElement;

      if (paneElement) {
        paneElement.addEventListener("pointerdown", this.onMeasurementPointerDown, {
          capture: true,
        });
      }
    },

    applyInteractionMode(): void {
      this.chartInfrastructure.setMouseDragScrollEnabled(this.interactionMode !== 'measure');

      if (this.interactionMode !== 'measure') {
        this.cancelMeasurementOverlay();
      }
    },

    onMeasurementPointerDown(event: PointerEvent): void {
      if (!this.canStartMeasurement(event)) {
        return;
      }

      const endpoint = this.resolveMeasurementEndpoint(event);
      if (!endpoint) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      this.activeMeasurement = {
        anchorPrice: endpoint.price,
        anchorLogical: endpoint.logical,
        minMove: this.currentMarketMinMove ?? 0,
      };
      this.addMeasurementWindowListeners();
      this.updateMeasurementOverlay(endpoint);
    },

    onMeasurementPointerMove(event: PointerEvent): void {
      if (!this.activeMeasurement) {
        return;
      }

      if ((event.buttons & 1) !== 1) {
        this.cancelMeasurementOverlay();
        return;
      }

      const endpoint = this.resolveMeasurementEndpoint(event);
      if (endpoint) {
        this.updateMeasurementOverlay(endpoint);
      }
    },

    onMeasurementPointerRelease(): void {
      this.cancelMeasurementOverlay();
    },

    canStartMeasurement(event: PointerEvent): boolean {
      return (
        this.interactionMode === 'measure' &&
        event.button === 0 &&
        (event.buttons & 1) === 1 &&
        this.activeMeasurement === null &&
        this.candlesticksStore.data.length > 0 &&
        this.ohlcSeriesRef !== null &&
        this.measurementPaneElement !== null
      );
    },

    resolveMeasurementEndpoint(event: PointerEvent): MeasurementEndpoint | null {
      const paneElement = this.measurementPaneElement;
      if (!paneElement) {
        return null;
      }

      const paneRect = paneElement.getBoundingClientRect();
      const x = event.clientX - paneRect.left;
      const y = event.clientY - paneRect.top;
      const price = this.chartInfrastructure.coordinateToCandlestickPrice(y);
      const logical = this.chartInfrastructure.coordinateToLogical(x);

      if (
        price === null ||
        logical === null ||
        !Number.isFinite(price) ||
        !Number.isFinite(logical)
      ) {
        return null;
      }

      return { price, logical };
    },

    updateMeasurementOverlay(endpoint: MeasurementEndpoint): void {
      const measurement = this.activeMeasurement;
      if (!measurement) {
        return;
      }

      this.chartInfrastructure.setCandlestickMeasurementOverlay(
        buildMeasurementOverlayModel({
          anchorPrice: measurement.anchorPrice,
          endpointPrice: endpoint.price,
          anchorLogical: measurement.anchorLogical,
          endpointLogical: endpoint.logical,
          minMove: measurement.minMove,
        }),
      );
    },

    addMeasurementWindowListeners(): void {
      window.addEventListener("pointermove", this.onMeasurementPointerMove);
      window.addEventListener("pointerup", this.onMeasurementPointerRelease);
      window.addEventListener("pointercancel", this.onMeasurementPointerRelease);
    },

    removeMeasurementWindowListeners(): void {
      window.removeEventListener("pointermove", this.onMeasurementPointerMove);
      window.removeEventListener("pointerup", this.onMeasurementPointerRelease);
      window.removeEventListener("pointercancel", this.onMeasurementPointerRelease);
    },

    cancelMeasurementOverlay(): void {
      if (!this.activeMeasurement) {
        return;
      }

      this.activeMeasurement = null;
      this.removeMeasurementWindowListeners();
      this.chartInfrastructure.clearCandlestickMeasurementOverlay();
    },

    getSeries() {
      return this.chartInfrastructure.getSeries();
    },

    async syncBacktestOverlayTarget(): Promise<void> {
      const paneHtmlElement = await this.chartInfrastructure.chartManager.getPaneHtmlElement(0);
      this.setMeasurementPaneElement(paneHtmlElement);
      this.backtestOverlayTarget = paneHtmlElement
        ? getOrCreatePaneOverlayWrapper(paneHtmlElement)
        : null;
    },

    addCandlestickData(
      data: readonly ChartCandle[],
      seriesOptions: CandlestickSeriesPartialOptions = {},
    ): ManagedSeriesApi | null {
      return this.chartInfrastructure.addCandlestickData(data, seriesOptions);
    },

    updateCandlestick(candle: ChartOhlcPoint): boolean {
      return this.chartInfrastructure.updateCandlestick(candle);
    },

    setMinMove(minMove: number): boolean {
      return this.chartInfrastructure.setMinMove(minMove);
    },

    subscribeCrosshairMove(callback: (param: MouseEventParams<Time>) => void): void {
      this.chartInfrastructure.subscribeCrosshairMove(callback);
    },

    subscribeVisibleLogicalRangeChange(callback: (range: ChartLogicalRange | null) => void): void {
      this.chartInfrastructure.subscribeVisibleLogicalRangeChange(callback);
    },

    scrollToRealTime(): void {
      this.chartInfrastructure.scrollToRealTime();
    },

    onWheelPassive(): void {
      this.lastWheelTs = performance.now();
      if (this.wheelSettleTimer !== null) {
        clearTimeout(this.wheelSettleTimer);
      }
      this.wheelSettleTimer = setTimeout(() => {
        this.wheelSettleTimer = null;
        if (this.latestVisibleRange) {
          this.onVisibleLogicalRangeChange(this.latestVisibleRange);
        }
      }, WHEEL_SETTLE_MS + 20);
    },

    scheduleIndicatorFlush(): void {
      if (this.indicatorFlushRafId !== null) return;
      this.indicatorFlushRafId = requestAnimationFrame(() => {
        this.indicatorFlushRafId = null;
        this.flushIndicatorUpdates();
      });
    },

    flushIndicatorUpdates(): void {
      if (this.pendingIndicatorMessages.size === 0) return;

      for (const [indicatorId, message] of this.pendingIndicatorMessages.entries()) {
        const point = this.indicatorsStore.handleLiveUpdate(message);
        if (!point) continue;
        this.indicatorManager.updateIndicatorSeriesPoint(indicatorId, point);
      }
      this.pendingIndicatorMessages.clear();
    },

    currentChartSessionKey(): ChartSessionKeyInput {
      return {
        symbol: this.currentMarketStore.symbol,
        exchange: this.currentMarketStore.exchange,
        timeframe: this.currentTimeframeStore.value,
      };
    },

    syncChartSession(): void {
      void this.chartSession?.setSession(this.currentChartSessionKey(), (message) => {
        this.updateCurrentCandle(message);
      });
    },

    renderCandlesticks(
      data: readonly ChartCandle[],
      { scrollToRealtime = false }: RenderCandlestickOptions = {},
    ): void {
      const minMove = this.currentMarketMinMove;
      if (minMove && minMove > 0) {
        this.seriesOptions.priceFormat = {
          type: "price",
          minMove,
          precision: Math.log10(1 / minMove),
        };
      }

      this.ohlcSeriesRef = this.addCandlestickData(data, this.seriesOptions);
      void this.syncBacktestOverlayTarget();
      this.refreshBacktestMarkers();

      if (scrollToRealtime) {
        this.scrollToRealTime();
        setTimeout(() => {
          this.shouldScrollToRealTime = false;
        }, 100);
      }
    },

    updateCurrentCandle(candle: CandleUpdateMessage): void {
      this.candlesticksStore.updateCandle(candle);
      this.updateCandlestick({
        timestamp_ms: candle.timestamp_ms,
        time: Math.floor(candle.timestamp_ms / 1000),
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume,
      });
      this.refreshBacktestMarkers();
    },

    getBacktestLoadedCandleRange(): LoadedCandleRange | null {
      if (this.candlesticksStore.data.length === 0) {
        return null;
      }

      let startMs = Number.POSITIVE_INFINITY;
      let endMs = Number.NEGATIVE_INFINITY;

      for (const candle of this.candlesticksStore.data) {
        startMs = Math.min(startMs, candle.timestamp_ms);
        endMs = Math.max(endMs, candle.timestamp_ms);
      }

      return { startMs, endMs };
    },

    refreshBacktestMarkers(): void {
      const range = this.getBacktestLoadedCandleRange();

      if (!this.backtestOverlayStore.selectedRun || !range) {
        this.chartInfrastructure.setCandlestickMarkers([]);
        this.chartInfrastructure.setCandlestickProtectiveLines([]);
        return;
      }

      const trades = this.backtestOverlayStore.getClosedTradesForRange(range.startMs, range.endMs);
      this.chartInfrastructure.setCandlestickMarkers(buildBacktestTradeMarkers(trades, range));
      this.chartInfrastructure.setCandlestickProtectiveLines(
        buildBacktestProtectiveLineSegments(trades),
      );
    },

    removeBacktestOverlay(): void {
      this.backtestOverlayStore.clearOverlay();
      this.refreshBacktestMarkers();
    },

    onCrosshairMove(param: MouseEventParams<Time>): void {
      try {
        const validCrosshairPoint = this.isValidCrosshairPoint(param);
        if (!validCrosshairPoint) {
          return;
        }

        this.latestCrosshairParam = param;
        if (this.crosshairRafId !== null) return;

        this.crosshairRafId = requestAnimationFrame(() => {
          this.crosshairRafId = null;
          const current = this.latestCrosshairParam;
          if (!current) return;

          const bar = this.ohlcSeriesRef ? current.seriesData.get(this.ohlcSeriesRef) : null;
          if (!isOhlcLegendPoint(bar)) return;

          this.updateLegend(bar);
        });
      } catch (error) {
        console.log("Error in crosshair move handler:", error);
      }
    },

    updateLegend(bar: OhlcLegendPoint): void {
      if (this.$refs.legendOpen instanceof HTMLElement) {
        this.$refs.legendOpen.textContent = String(bar.open ?? "-");
      }
      if (this.$refs.legendHigh instanceof HTMLElement) {
        this.$refs.legendHigh.textContent = String(bar.high ?? "-");
      }
      if (this.$refs.legendLow instanceof HTMLElement) {
        this.$refs.legendLow.textContent = String(bar.low ?? "-");
      }
      if (this.$refs.legendClose instanceof HTMLElement) {
        this.$refs.legendClose.textContent = String(bar.close ?? "-");
      }
    },

    onVisibleLogicalRangeChange(newVisibleLogicalRange: ChartLogicalRange | null): void {
      this.latestVisibleRange = newVisibleLogicalRange;
      if (this.visibleRangeRafId !== null) return;

      this.visibleRangeRafId = requestAnimationFrame(() => {
        this.visibleRangeRafId = null;
        const range = this.latestVisibleRange;
        if (!range) return;

        const ohlc = this.getSeries().get('ohlc');
        if (!ohlc) return;

        const barsInfo = ohlc.series.barsInLogicalRange(range);
        if (barsInfo === null) return;
        const now = performance.now();
        if ((now - this.lastWheelTs) < WHEEL_SETTLE_MS) {
          return;
        }

        this.chartSession?.requestOlderHistory({
          barsBefore: barsInfo.barsBefore,
          nowMs: now,
          scrollToRealtime: this.shouldScrollToRealTime,
        });
      });
    },

    isValidCrosshairPoint(
      param: MouseEventParams<Time> | undefined,
    ): param is MouseEventParams<Time> & { time: Time; point: Point } {
      return (
        param !== undefined &&
        param.time !== undefined &&
        param.point !== undefined &&
        param.point.x >= 0 &&
        param.point.y >= 0
      );
    },

    getAllIndicators() {
      return this.indicatorsStore.all;
    },

    getIndicatorLoadedCandleRange(timeframe: string) {
      const firstCandle = this.candlesticksStore.data[0];
      const lastCandle = this.candlesticksStore.data[this.candlesticksStore.data.length - 1];
      if (!firstCandle || !lastCandle) return null;

      return {
        oldestTimestampMs: firstCandle.timestamp_ms,
        newestTimestampMs: lastCandle.timestamp_ms,
        exclusiveEndMs: lastCandle.timestamp_ms + timeframeToMinutes(timeframe) * 60_000,
      };
    },
  },
});
</script>

<style scoped>
#chart-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.chart-container {
  width: 100%;
  height: 100%;
}

.chart-container--measure-mode,
.chart-container--measure-mode :deep(*) {
  cursor: crosshair;
}

.backtest-overlay-container {
  margin-bottom: 8px;
}

.backtest-overlay-panel {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 300px;
  width: min(350px, calc(100vw - 20px));
  max-width: 100%;
  padding: 8px 12px;
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.3;
  background: rgba(19, 23, 34, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
}

.backtest-overlay-details {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  flex: 1 1 auto;
  gap: 4px 8px;
  min-width: 0;
}

.backtest-overlay-title {
  font-weight: 700;
  color: #f8fafc;
}

.backtest-overlay-context {
  flex: 1 1 160px;
  min-width: 0;
  overflow: hidden;
  color: #cbd5e1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.backtest-overlay-remove {
  flex: 0 0 auto;
  color: #f8fafc;
}

.backtest-overlay-remove:hover {
  color: #e98b8b;
}

.legend {
  position: absolute;
  top: 50px;
  left: 10px;
}

.legend-value {
  margin-right: 10px;
}
</style>
