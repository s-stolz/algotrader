<template>
  <div id="chart-wrapper">
    <div ref="chartContainer" id="lightweight-chart" class="chart-container" />

    <span class="legend" v-if="candlestickOhlc">
      <span v-for="(legend, key) in candlestickOhlc" :key="key" class="legend-value">
        {{ legend.label }}: {{ legend.value }}
      </span>
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

import { ChartMixin } from "@/utils/chart";
import Indicator from "@/components/Chart/Indicator/Indicator.vue";

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
      crossHairTimeout: null,
      candlestickOhlc: undefined,
      isFetchingCandles: false,
      candlesFetchLimit: 5000,
      isFetchingIndicators: false,
      indicatorBatchSize: 5000,
      shouldScrollToRealTime: false,
      messageHandler: null,
      candlesFetchPromise: null,
      candlesFetchKey: null,
    };
  },

  computed: {
    currentMarketMinMove() {
      return this.currentMarketStore.min_move;
    },
  },

  watch: {
    currentMarketMinMove(newMinMove) {
      if (newMinMove && newMinMove > 0) {
        this.setMinMove(newMinMove);
      }
    },

    "currentMarketStore.symbol_id": {
      handler(newSymbol, oldSymbol) {
        this.indicatorsStore.resetHistoryFlags();
        this.shouldScrollToRealTime = true;
        this.fetchCandlesticks();

        if (newSymbol !== oldSymbol) {
          this.subscribeToCandles();
        }
      },
      immediate: true,
    },

    "currentTimeframeStore.value": {
      handler(newTimeframe, oldTimeframe) {
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
  },

  methods: {
    async initializeChartComponent() {
      this.subscribeCrosshairMove(this.onCrosshairMove);
      this.subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChange);
    },

    async fetchCandlesticks() {
      if (this.currentMarketStore.symbol_id === null) return;

      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;
      const fetchKey = `${symbolID}:${timeframe}:${this.candlesFetchLimit}`;

      if (this.candlesFetchPromise && this.candlesFetchKey === fetchKey) {
        await this.candlesFetchPromise;
        return;
      }

      this.candlesFetchKey = fetchKey;
      this.candlesFetchPromise = (async () => {
        await this.candlesticksStore.fetch(symbolID, timeframe, null, null, this.candlesFetchLimit);
        this.renderCandlesticks(this.candlesticksStore.data, { scrollToRealtime: this.shouldScrollToRealTime });
        this.indicatorsStore.requestAllIndicators(symbolID, timeframe);
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
      this.addCandlestickData(data, this.seriesOptions);

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
        if (
          message.type === 'candleUpdate' &&
          message.symbol === symbol &&
          message.timeframe === 'M1'
        ) {
          this.updateCurrentCandleWithM1(message);
        }
      };

      wsService.on('message', this.messageHandler);

      try {
        await wsService.send('subscribeCandles', { symbol, timeframe });
      } catch (error) {
        console.error('Failed to subscribe:', error);
      }
    },

    async unsubscribeFromCandles() {
      if (this.messageHandler) {
        wsService.off('message', this.messageHandler);
        this.messageHandler = null;
      }

      const symbol = this.currentMarketStore.symbol;
      const timeframe = this.currentTimeframeStore.value;

      if (symbol && timeframe !== null) {
        await wsService.send('unsubscribeCandles', { symbol, timeframe });
      }
    },

    updateCurrentCandleWithM1(m1Candle) {
      if (!this.candlesticksStore.data || this.candlesticksStore.data.length === 0) {
        return;
      }

      const timeframeMinutes = this.currentTimeframeStore.value;
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
        if (this.crossHairTimeout != null) {
          clearTimeout(this.crossHairTimeout);
        }

        const validCrosshairPoint = this.isValidCrosshairPoint(param);
        if (!validCrosshairPoint) {
          return;
        }

        this.crossHairTimeout = setTimeout(() => {
          const bar = Array.from(param.seriesData.values())[0];

          if (!bar) {
            return;
          }
          this.candlestickOhlc = {
            open: { label: "O", value: bar.open },
            high: { label: "H", value: bar.high },
            low: { label: "L", value: bar.low },
            close: { label: "C", value: bar.close },
          };

          this.crossHairTimeout = null;
        }, 10);
      } catch (error) {
        console.log("Error in crosshair move handler:", error);
      }
    },

    onVisibleLogicalRangeChange(newVisibleLogicalRange) {
      if (this.shouldScrollToRealTime) return;

      const series = this.getSeries();

      for (const [, value] of series.entries()) {
        const barsInfo = value.series.barsInLogicalRange(newVisibleLogicalRange);

        if (barsInfo === null) continue;

        if (barsInfo.barsBefore < 100 && !this.isFetchingCandles) {
          this.isFetchingCandles = true;
          this.loadMoreBars();
        }

        if (barsInfo.barsBefore < 100 && !this.isFetchingIndicators) {
          this.isFetchingIndicators = true;
          this.loadMoreIndicatorHistory();
        }
      }
    },

    async loadMoreBars() {
      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;
      if (!this.candlesticksStore.data.length) {
        this.isFetchingCandles = false;
        return;
      }
      const firstBarTimestampMs = this.candlesticksStore.data[0].timestamp_ms;

      await this.candlesticksStore.fetch(
        symbolID,
        timeframe,
        null,
        firstBarTimestampMs,
        this.candlesFetchLimit,
        true,
      );
      this.renderCandlesticks(this.candlesticksStore.data);
      this.isFetchingCandles = false;
    },

    async loadMoreIndicatorHistory() {
      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;

      try {
        await this.indicatorsStore.fetchOlderForAll(symbolID, timeframe, this.indicatorBatchSize);
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
