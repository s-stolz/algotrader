<template>
  <div id="chart-wrapper">
    <div ref="chartContainer" id="lightweight-chart" class="chart-container" />

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
import { markRaw, defineComponent } from "vue";
import type {
  CandlestickSeriesPartialOptions,
  MouseEventParams,
  Point,
  Time,
} from "lightweight-charts";

import { useCandlesticksStore } from "@/stores/candlesticksStore";
import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
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
  type ChartSessionSubscriptionsAdapter,
  type ChartSessionKeyInput,
} from "@/components/Chart/chartSession";

import {
  createChartInfrastructure,
  type ChartInfrastructure,
  type ChartLogicalRange,
  type ChartOhlcPoint,
  type ManagedSeriesApi,
} from "@/utils/chart";
import Indicator from "@/components/Chart/Indicator/Indicator.vue";

const HISTORY_LOAD_COOLDOWN_MS = 400;
const WHEEL_SETTLE_MS = 250;

type CandlesticksStore = ReturnType<typeof useCandlesticksStore>;
type IndicatorsStore = ReturnType<typeof useIndicatorsStore>;
type CurrentMarketStore = ReturnType<typeof useCurrentMarketStore>;
type CurrentTimeframeStore = ReturnType<typeof useCurrentTimeframeStore>;

interface OhlcLegendPoint {
  open?: number;
  high?: number;
  low?: number;
  close?: number;
}

interface RenderCandlestickOptions {
  scrollToRealtime?: boolean;
}

interface ChartAreaData {
  candlesticksStore: CandlesticksStore;
  indicatorsStore: IndicatorsStore;
  currentMarketStore: CurrentMarketStore;
  currentTimeframeStore: CurrentTimeframeStore;
  chartInfrastructure: ChartInfrastructure;
  seriesOptions: CandlestickSeriesPartialOptions;
  crosshairRafId: number | null;
  latestCrosshairParam: MouseEventParams<Time> | null;
  visibleRangeRafId: number | null;
  latestVisibleRange: ChartLogicalRange | null;
  indicatorFlushRafId: number | null;
  pendingIndicatorMessages: Map<string, IndicatorUpdateMessage>;
  ohlcSeriesRef: ManagedSeriesApi | null;
  isFetchingCandles: boolean;
  lastCandlesHistoryLoadTs: number;
  lastWheelTs: number;
  wheelSettleTimer: ReturnType<typeof setTimeout> | null;
  candlesFetchLimit: number;
  isFetchingIndicators: boolean;
  lastIndicatorsHistoryLoadTs: number;
  indicatorBatchSize: number;
  shouldScrollToRealTime: boolean;
  indicatorMessageHandler: WebSocketEventHandler<"indicatorUpdate"> | null;
  chartSession: ChartSession | null;
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
    Indicator,
  },

  data(): ChartAreaData {
    return {
      candlesticksStore: useCandlesticksStore(),
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
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
      isFetchingCandles: false,
      lastCandlesHistoryLoadTs: 0,
      lastWheelTs: 0,
      wheelSettleTimer: null,
      candlesFetchLimit: 500,
      isFetchingIndicators: false,
      lastIndicatorsHistoryLoadTs: 0,
      indicatorBatchSize: 500,
      shouldScrollToRealTime: false,
      indicatorMessageHandler: null,
      chartSession: null,
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
    const chartContainer = this.getChartContainer();
    if (chartContainer) {
      chartContainer.removeEventListener("wheel", this.onWheelPassive);
    }
    this.chartInfrastructure.cleanup();
  },

  methods: {
    createChartSessionAdapter(): ChartSessionSubscriptionsAdapter {
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
          this.indicatorsStore.requestAllIndicators(key.symbol, key.timeframe, key.exchange);
        },
        unsubscribeIndicators: () => this.indicatorsStore.unsubscribeAllLive(),
        resetIndicatorHistory: () => {
          this.indicatorsStore.resetHistoryFlags();
        },
        reportCandleFetchError: (_key, error) => {
          console.error('Failed to fetch candlestick data:', error);
        },
        reportSubscriptionError: (operation, _key, error) => {
          console.error(`Failed to ${operation} candle subscription:`, error);
        },
      };
    },

    initializeChartComponent(): void {
      this.chartInfrastructure.init(this.getChartContainer());
      this.subscribeCrosshairMove(this.onCrosshairMove);
      this.subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChange);
      const chartContainer = this.getChartContainer();
      if (chartContainer) {
        chartContainer.addEventListener("wheel", this.onWheelPassive, { passive: true });
      }
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

    getSeries() {
      return this.chartInfrastructure.getSeries();
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
      if (this.shouldScrollToRealTime) return;
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

        if (
          barsInfo.barsBefore < 100 &&
          !this.isFetchingCandles &&
          (now - this.lastCandlesHistoryLoadTs) >= HISTORY_LOAD_COOLDOWN_MS
        ) {
          this.lastCandlesHistoryLoadTs = now;
          this.isFetchingCandles = true;
          void this.loadMoreBars();
        }

        if (
          barsInfo.barsBefore < 100 &&
          !this.isFetchingIndicators &&
          (now - this.lastIndicatorsHistoryLoadTs) >= HISTORY_LOAD_COOLDOWN_MS
        ) {
          this.lastIndicatorsHistoryLoadTs = now;
          this.isFetchingIndicators = true;
          void this.loadMoreIndicatorHistory();
        }
      });
    },

    async loadMoreBars(): Promise<void> {
      const symbol = this.currentMarketStore.symbol;
      const exchange = this.currentMarketStore.exchange;
      const timeframe = this.currentTimeframeStore.value;
      if (!this.candlesticksStore.data.length) {
        this.isFetchingCandles = false;
        return;
      }
      const firstBarTimestampMs = this.candlesticksStore.data[0].timestamp_ms;

      await this.candlesticksStore.fetch(symbol, timeframe, {
        endMs: firstBarTimestampMs,
        limit: this.candlesFetchLimit,
        append: true,
        exchange: exchange,
      });
      this.renderCandlesticks(this.candlesticksStore.data);
      this.isFetchingCandles = false;
    },

    async loadMoreIndicatorHistory(): Promise<void> {
      const symbol = this.currentMarketStore.symbol;
      const exchange = this.currentMarketStore.exchange;
      const timeframe = this.currentTimeframeStore.value;

      try {
        await this.indicatorsStore.fetchOlderForAll(
          symbol,
          timeframe,
          exchange,
          this.indicatorBatchSize,
        );
      } finally {
        this.isFetchingIndicators = false;
      }
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

.legend {
  position: absolute;
  top: 50px;
  left: 10px;
}

.legend-value {
  margin-right: 10px;
}
</style>
