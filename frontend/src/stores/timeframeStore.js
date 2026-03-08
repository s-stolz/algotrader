import { defineStore } from 'pinia';

export const useTimeframeStore = defineStore('timeframe', {
  state: () => ({
    currentTimeframe: { name: 'M1', value: 'M1' },
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
