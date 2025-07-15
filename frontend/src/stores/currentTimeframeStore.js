import { defineStore } from 'pinia';

export const useCurrentTimeframeStore = defineStore('currentTimeframe', {
  state: () => ({
    label: '1M',
    value: 1,
  }),
  actions: {
    setCurrentTimeframe(timeframe) {
      this.label = timeframe.label;
      this.value = timeframe.value;
    },
  },
});
