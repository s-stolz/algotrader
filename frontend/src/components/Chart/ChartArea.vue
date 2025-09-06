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
        :key="indicator.id"
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
          minMove: 0.00001,
          precision: 5,
        },
      },
      crossHairTimeout: null,
      candlestickOhlc: undefined,
      isFetchingCandles: false,
      candlesFetchLimit: 5000,
    };
  },

  computed: {
    currentMarketMinMove() {
      return this.currentMarketStore.min_move;
    },
  },

  watch: {
    "candlesticksStore.data": {
      handler(newData) {
        this.setMinMove(this.currentMarketMinMove);
        this.addCandlestickData(newData, this.seriesOptions);
        this.indicatorsStore.requestAllIndicators(
          this.currentMarketStore.symbol_id,
          this.currentTimeframeStore.value,
        );
      },
      deep: true,
    },

    "currentMarketStore.symbol_id": {
      handler() {
        this.fetchCandlesticks();
      },
      immediate: true,
    },

    "currentTimeframeStore.value": {
      handler() {
        this.fetchCandlesticks();
      },
      immediate: true,
    },
  },

  mounted() {
    this.initializeChartComponent();
  },

  methods: {
    async initializeChartComponent() {
      this.subscribeCrosshairMove(this.onCrosshairMove);
      this.subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChange);

      await this.fetchCandlesticks();
    },

    async fetchCandlesticks() {
      if (this.currentMarketStore.symbol_id === null) return;

      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;

      await this.candlesticksStore.fetch(symbolID, timeframe, null, null, this.candlesFetchLimit);
    },

    setMinMove(minMove) {
      this.seriesOptions.priceFormat.minMove = minMove;
      this.seriesOptions.priceFormat.precision = Math.log10(1 / minMove);
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
      const series = this.getSeries();

      for (const [, value] of series.entries()) {
        const barsInfo = value.series.barsInLogicalRange(newVisibleLogicalRange);

        if (barsInfo !== null && barsInfo.barsBefore < 100 && !this.isFetchingCandles) {
          this.isFetchingCandles = true;

          this.loadMoreBars();
        }
      }
    },

    async loadMoreBars() {
      const symbolID = this.currentMarketStore.symbol_id;
      const timeframe = this.currentTimeframeStore.value;
      const firstBarTime = this.candlesticksStore.data[0].time;
      const firstBarDate = new Date(firstBarTime * 1000).toISOString().slice(0, -5);

      await this.candlesticksStore.fetch(symbolID, timeframe, null, firstBarDate, this.candlesFetchLimit, true);
      this.isFetchingCandles = false;
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
