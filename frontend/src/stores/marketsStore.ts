import { fetchMarkets } from '@/api/marketClient';
import type { Market } from '@/types/contracts';
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useMarketsStore = defineStore('markets', () => {
  const all = ref<Market[]>([]);

  async function fetch(): Promise<void> {
    try {
      all.value = await fetchMarkets();
    } catch (err) {
      console.error('Failed to fetch markets:', err);
    }
  }

  return {
    all,
    fetch,
  };
});
