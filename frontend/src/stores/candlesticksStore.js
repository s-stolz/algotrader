import { defineStore } from 'pinia';

export const useCandlesticksStore = defineStore('candlesticks', {
  state: () => ({
    type: 'candlestick',
    data: [],
  }),

  actions: {
    async fetch(symbol, timeframe, {
      startMs = null,
      endMs = null,
      limit = null,
      append = false,
      exchange = null,
    } = {}) {
      const optionalParams = new URLSearchParams();
      if (startMs) optionalParams.append('start_ms', startMs);
      if (endMs) optionalParams.append('end_ms', endMs);
      if (limit) optionalParams.append('limit', limit);
      if (exchange) optionalParams.append('exchange', exchange);

      try {
        const response = await fetch(
          `/api/data-accessor/candles/${symbol}?timeframe=${timeframe}&${optionalParams.toString()}`,
        );
        let newData = await response.json();

        newData = newData.map((candle) => {
          return {
            timestamp_ms: candle.timestamp_ms,
            time: Math.floor(candle.timestamp_ms / 1000),
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
          };
        });

        if (append) {
          this.data = [...newData, ...this.data];
        } else {
          this.data = newData;
        }
      } catch (err) {
        console.error('Failed to fetch candlestick data:', err);
      }
    },

    updateCandle(candleData) {
      if (!candleData?.timestamp_ms) return;

      const newCandle = {
        timestamp_ms: candleData.timestamp_ms,
        time: Math.floor(candleData.timestamp_ms / 1000),
        open: candleData.open,
        high: candleData.high,
        low: candleData.low,
        close: candleData.close,
      };

      const existingIndex = this.data.findIndex(candle => candle.time === newCandle.time);

      if (existingIndex >= 0) {
        this.data[existingIndex] = newCandle;
      } else {
        this.data.push(newCandle);
      }
    },

    clear() {
      this.data = [];
    },
  },
});
