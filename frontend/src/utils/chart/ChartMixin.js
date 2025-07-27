import { ChartManager } from './ChartManager.js';
import { IndicatorManager } from './IndicatorManager.js';

export const ChartMixin = {
  data() {
    return {
      chartManager: null,
      indicatorManager: null,
      chartInitialized: false,
      chartError: null,
    };
  },

  mounted() {
    this.initializeChart();
  },

  beforeUnmount() {
    this.cleanupChart();
  },

  methods: {
    initializeChart() {
      try {
        this.chartManager = new ChartManager(this.getChartOptions());
        this.indicatorManager = new IndicatorManager(this.chartManager);

        if (this.$refs.chartContainer) {
          this.chartInitialized = this.chartManager.init(
            this.$refs.chartContainer,
          );
        }
      } catch (error) {
        console.error('Failed to initialize chart:', error);
        this.chartError = error;
      }
    },

    getChartOptions() {
      return this.chartOptions || {};
    },

    addCandlestickData(data, seriesOptions = {}) {
      const defaultOptions = {
        priceFormat: {
          type: 'price',
          minMove: 0.00001,
        },
        ...seriesOptions,
      };

      return this.chartManager.addSeries('ohlc', 'candlestick', data, defaultOptions);
    },

    subscribeCrosshairMove(callback) {
      this.chartManager.subscribeCrosshairMove(callback);
    },

    cleanupChart() {
      if (this.indicatorManager) {
        this.indicatorManager.destroy();
        this.indicatorManager = null;
      }

      if (this.chartManager) {
        this.chartManager.destroy();
        this.chartManager = null;
      }

      this.chartInitialized = false;
    },
  },
};
