import { defineStore } from 'pinia';

export const useTimeframeStore = defineStore('timeframe', {
  state: () => ({
    currentTimeframe: { name: '1M', value: 1 },
  }),
  actions: {
    setCurrentTimeframe(timeframe) {
      this.currentTimeframe = timeframe;
    },
    getCurrentTimeframe() {
      return this.currentTimeframe;
    },
  },
});
