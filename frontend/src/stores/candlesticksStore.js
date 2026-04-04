import { defineStore } from 'pinia';
import { markRaw } from 'vue';

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
          this.data = markRaw([...newData, ...this.data]);
        } else {
          this.data = markRaw(newData);
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

      const last = this.data[this.data.length - 1];
      if (!last) {
        this.data.push(newCandle);
        return;
      }

      if (last.time === newCandle.time) {
        const isNoOp = (
          last.open === newCandle.open &&
          last.high === newCandle.high &&
          last.low === newCandle.low &&
          last.close === newCandle.close
        );
        if (!isNoOp) {
          this.data[this.data.length - 1] = newCandle;
        }
        return;
      }

      if (last.time < newCandle.time) {
        this.data.push(newCandle);
      }
    },

    clear() {
      this.data = markRaw([]);
    },
  },
});
