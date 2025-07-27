import { defineStore } from 'pinia';

export const useMarketsStore = defineStore('markets', {
  state: () => ({
    all: [],
  }),

  actions: {
    async fetch() {
      try {
        const response = await fetch('/api/data-accessor/markets');
        const data = await response.json();

        this.all = data;
      } catch (err) {
        console.error('Failed to fetch markets:', err);
      }
    },
  },
});
