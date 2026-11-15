import { useCurrentMarketStore } from './currentMarketStore';
import { fetchMarkets } from '@/api/marketClient';
import type { Market } from '@/types/contracts';
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useMarketsStore = defineStore('markets', () => {
  const all = ref<Market[]>([]);

  const fetchError = ref<string | null>(null);

  async function fetch(): Promise<void> {
    fetchError.value = null;
    try {
      all.value = await fetchMarkets();
      const current = useCurrentMarketStore();
      const refreshed = all.value.find(
        (market) => market.symbol_id === current.symbol_id,
      );
      if (refreshed) current.setMarket(refreshed);
    } catch (err) {
      fetchError.value = 'Couldn’t load markets.';
      console.error('Failed to fetch markets:', err);
    }
  }

  return {
    all,
    fetchError,
    fetch,
  };
});
