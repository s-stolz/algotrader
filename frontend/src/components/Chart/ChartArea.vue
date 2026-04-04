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

<script>
import { useCandlesticksStore } from "@/stores/candlesticksStore";
import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
import { wsService } from "@/utils/websocketService";
import { timeframeToMinutes } from "@/utils/timeframes";

import { ChartMixin } from "@/utils/chart";
import Indicator from "@/components/Chart/Indicator/Indicator.vue";

const HISTORY_LOAD_COOLDOWN_MS = 400;
const WHEEL_SETTLE_MS = 250;

export default {
  name: "ChartArea",

  components: {
    Indicator,
  },

  mixins: [ChartMixin],

  data() {
    return {
      candlesticksStore: useCandlesticksStore(),
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      seriesOptions: {
        priceFormat: {
          type: "price",
          minMove: null,
          precision: null,
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
      messageHandler: null,
      indicatorMessageHandler: null,
      candlesFetchPromise: null,
      candlesFetchKey: null,
    };
  },

  computed: {
    currentMarketMinMove() {
      return this.currentMarketStore.min_move;
    },

    currentMarketKey() {
      const symbol = this.currentMarketStore.symbol || "";
      const exchange = this.currentMarketStore.exchange || "";
      return `${symbol}|${exchange}`;
    },
  },

  watch: {
    currentMarketMinMove(newMinMove) {
      if (newMinMove && newMinMove > 0) {
        this.setMinMove(newMinMove);
      }
    },

    currentMarketKey: {
      handler(newKey, oldKey) {
        this.indicatorsStore.unsubscribeAllLive();
        this.indicatorsStore.resetHistoryFlags();
        this.shouldScrollToRealTime = true;
        this.fetchCandlesticks();

        if (newKey !== oldKey) {
          this.subscribeToCandles();
        }
      },
      immediate: true,
    },

    "currentTimeframeStore.value": {
      handler(newTimeframe, oldTimeframe) {
        this.indicatorsStore.unsubscribeAllLive();
        this.indicatorsStore.resetHistoryFlags();
        this.shouldScrollToRealTime = true;
        this.fetchCandlesticks();

        if (newTimeframe !== oldTimeframe) {
          this.subscribeToCandles();
        }
      },
      immediate: true,
    },
  },

  mounted() {
    this.initializeChartComponent();
  },

  beforeUnmount() {
    this.unsubscribeFromCandles();
    this.indicatorsStore.unsubscribeAllLive();
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
    if (this.$refs.chartContainer) {
      this.$refs.chartContainer.removeEventListener('wheel', this.onWheelPassive);
    }
  },

  methods: {
    async initializeChartComponent() {
      this.subscribeCrosshairMove(this.onCrosshairMove);
      this.subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChange);
      if (this.$refs.chartContainer) {
        this.$refs.chartContainer.addEventListener('wheel', this.onWheelPassive, { passive: true });
      }
      this.indicatorMessageHandler = (message) => {
        if (!message?.clientIndicatorId) return;
        this.pendingIndicatorMessages.set(message.clientIndicatorId, message);
        this.scheduleIndicatorFlush();
      };
      wsService.on('indicatorUpdate', this.indicatorMessageHandler);
    },

    onWheelPassive() {
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

    scheduleIndicatorFlush() {
      if (this.indicatorFlushRafId !== null) return;
      this.indicatorFlushRafId = requestAnimationFrame(() => {
        this.indicatorFlushRafId = null;
        this.flushIndicatorUpdates();
      });
    },

    flushIndicatorUpdates() {
      if (this.pendingIndicatorMessages.size === 0) return;

      for (const [indicatorId, message] of this.pendingIndicatorMessages.entries()) {
        const point = this.indicatorsStore.handleLiveUpdate(message);
        if (!point) continue;
        this.indicatorManager.updateIndicatorSeriesPoint(indicatorId, point);
      }
      this.pendingIndicatorMessages.clear();
    },

    async fetchCandlesticks() {
      if (!this.currentMarketStore.symbol) return;

      const symbol = this.currentMarketStore.symbol;
      const exchange = this.currentMarketStore.exchange;
      const timeframe = this.currentTimeframeStore.value;
      const fetchKey = `${symbol}:${exchange || ""}:${timeframe}:${this.candlesFetchLimit}`;

      if (this.candlesFetchPromise && this.candlesFetchKey === fetchKey) {
        await this.candlesFetchPromise;
        return;
      }

      this.candlesFetchKey = fetchKey;
      this.candlesFetchPromise = (async () => {
        await this.candlesticksStore.fetch(symbol, timeframe, {
          limit: this.candlesFetchLimit,
          exchange: exchange,
        });
        this.renderCandlesticks(this.candlesticksStore.data, { scrollToRealtime: this.shouldScrollToRealTime });
        this.indicatorsStore.requestAllIndicators(symbol, timeframe, exchange);
      })();

      try {
        await this.candlesFetchPromise;
      } finally {
        if (this.candlesFetchKey === fetchKey) {
          this.candlesFetchPromise = null;
        }
      }
    },

    renderCandlesticks(data, { scrollToRealtime = false } = {}) {
      this.seriesOptions.priceFormat.minMove = this.currentMarketMinMove;
      this.seriesOptions.priceFormat.precision = Math.log10(1 / this.currentMarketMinMove);
      this.ohlcSeriesRef = this.addCandlestickData(data, this.seriesOptions);

      if (scrollToRealtime) {
        this.scrollToRealTime();
        setTimeout(() => {
          this.shouldScrollToRealTime = false;
        }, 100);
      }
    },

    async subscribeToCandles() {
      this.unsubscribeFromCandles();

      const symbol = this.currentMarketStore.symbol;
      const timeframe = this.currentTimeframeStore.value;

      if (!symbol || timeframe === null) return;

      this.messageHandler = (message) => {
        if (message.symbol !== symbol) {
          return;
        }

        if (message.timeframe === timeframe) {
          this.updateCurrentCandle(message);
          return;
        }

        if (message.timeframe === 'M1') {
          this.updateCurrentCandleFromM1(message);
        }
      };

      wsService.on('candleUpdate', this.messageHandler);

      try {
        await wsService.send('subscribeCandles', { symbol, timeframe });
      } catch (error) {
        console.error('Failed to subscribe:', error);
      }
    },

    async unsubscribeFromCandles() {
      if (this.messageHandler) {
        wsService.off('candleUpdate', this.messageHandler);
        this.messageHandler = null;
      }

      const symbol = this.currentMarketStore.symbol;
      const timeframe = this.currentTimeframeStore.value;

      if (symbol && timeframe !== null) {
        await wsService.send('unsubscribeCandles', { symbol, timeframe });
      }
    },

    updateCurrentCandle(candle) {
      this.candlesticksStore.updateCandle(candle);
      this.updateCandlestick({
        timestamp_ms: candle.timestamp_ms,
        time: Math.floor(candle.timestamp_ms / 1000),
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      });
    },

    updateCurrentCandleFromM1(m1Candle) {
      if (!this.candlesticksStore.data || this.candlesticksStore.data.length === 0) {
        return;
      }

      const timeframeMinutes = timeframeToMinutes(this.currentTimeframeStore.value);
      const timeframeMs = timeframeMinutes * 60 * 1000;
      const bucketTimestampMs = Math.floor(m1Candle.timestamp_ms / timeframeMs) * timeframeMs;
      const candleTimeSeconds = Math.floor(bucketTimestampMs / 1000);

      const lastCandle = this.candlesticksStore.data[this.candlesticksStore.data.length - 1];

      let updatedCandle;

      if (lastCandle.timestamp_ms === bucketTimestampMs) {
        updatedCandle = {
          timestamp_ms: bucketTimestampMs,
          time: candleTimeSeconds,
          open: lastCandle.open,
          high: Math.max(lastCandle.high, m1Candle.high),
          low: Math.min(lastCandle.low, m1Candle.low),
          close: m1Candle.close,
        };
        this.candlesticksStore.data[this.candlesticksStore.data.length - 1] = updatedCandle;
      } else if (bucketTimestampMs > lastCandle.timestamp_ms) {
        updatedCandle = {
          timestamp_ms: bucketTimestampMs,
          time: candleTimeSeconds,
          open: m1Candle.open,
          high: m1Candle.high,
          low: m1Candle.low,
          close: m1Candle.close,
        };
        this.candlesticksStore.data.push(updatedCandle);
      } else {
        return;
      }

      this.updateCandlestick(updatedCandle);
    },

    onCrosshairMove(param) {
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
          if (!bar) return;

          this.updateLegend(bar);
        });
      } catch (error) {
        console.log("Error in crosshair move handler:", error);
      }
    },

    updateLegend(bar) {
      if (this.$refs.legendOpen) this.$refs.legendOpen.textContent = String(bar.open ?? "-");
      if (this.$refs.legendHigh) this.$refs.legendHigh.textContent = String(bar.high ?? "-");
      if (this.$refs.legendLow) this.$refs.legendLow.textContent = String(bar.low ?? "-");
      if (this.$refs.legendClose) this.$refs.legendClose.textContent = String(bar.close ?? "-");
    },

    onVisibleLogicalRangeChange(newVisibleLogicalRange) {
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
          this.loadMoreBars();
        }

        if (
          barsInfo.barsBefore < 100 &&
          !this.isFetchingIndicators &&
          (now - this.lastIndicatorsHistoryLoadTs) >= HISTORY_LOAD_COOLDOWN_MS
        ) {
          this.lastIndicatorsHistoryLoadTs = now;
          this.isFetchingIndicators = true;
          this.loadMoreIndicatorHistory();
        }
      });
    },

    async loadMoreBars() {
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

    async loadMoreIndicatorHistory() {
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

    isValidCrosshairPoint(param) {
      return (
        param !== undefined &&
        param.time !== undefined &&
        param.point.x >= 0 &&
        param.point.y >= 0
      );
    },

    getAllIndicators() {
      return this.indicatorsStore.all;
    },
  },
};
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
