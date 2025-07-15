import { defineStore } from 'pinia';

export const useCandlesticksStore = defineStore('candlesticks', {
  state: () => ({
    type: 'candlestick',
    data: [],
  }),

  actions: {
    async fetch(symbolID, timeframe) {
      try {
        const response = await fetch(`/api/candles/${symbolID}/${timeframe}`);
        const data = await response.json();

        this.data = data.map((candle) => {
          const utc = new Date(candle.timestamp).getTime() / 1000;
          return {
            time: utc,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
          };
        });
      } catch (err) {
        console.error('Failed to fetch candlestick data:', err);
      }
    },
  }
});