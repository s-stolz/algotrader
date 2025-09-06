import { defineStore } from 'pinia';

export const useCandlesticksStore = defineStore('candlesticks', {
  state: () => ({
    type: 'candlestick',
    data: [],
  }),

  actions: {
    async fetch(symbolID, timeframe, startDate = null, endDate = null, limit = null, append = false) {
      const optionalParams = new URLSearchParams();
      if (startDate) optionalParams.append('start_date', startDate);
      if (endDate) optionalParams.append('end_date', endDate);
      if (limit) optionalParams.append('limit', limit);

      try {
        const response = await fetch(
          `/api/data-accessor/candles/${symbolID}?timeframe=${timeframe}&${optionalParams.toString()}`,
        );
        let newData = await response.json();

        newData = newData.map((candle) => {
          const utc = new Date(`${candle.timestamp}Z`).getTime() / 1000;
          return {
            time: utc,
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
  },
});