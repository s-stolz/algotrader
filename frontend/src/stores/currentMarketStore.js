import { getStoredState, setStoredState, STORAGE_KEYS } from "@/utils/localStorage";
import { defineStore } from "pinia";

export const useCurrentMarketStore = defineStore('currentMarket', {
  state: () => {
    const stored = getStoredState(STORAGE_KEYS.CURRENT_MARKET);

    return {
      exchange: stored?.exchange ?? null,
      market_type: stored?.market_type ?? null,
      min_move: stored?.min_move ?? null,
      symbol: stored?.symbol ?? null,
      symbol_id: stored?.symbol_id ?? null,
    };
  },

  actions: {
    setMarket(market) {
      Object.assign(this, market);

      setStoredState(STORAGE_KEYS.CURRENT_MARKET, {
        exchange: this.exchange,
        market_type: this.market_type,
        min_move: this.min_move,
        symbol: this.symbol,
        symbol_id: this.symbol_id,
      });
    },

    isValid(availableMarkets) {
      if (!this.symbol) return false;
      return availableMarkets.some(m => {
        if (m.symbol !== this.symbol) return false;
        if (this.exchange) {
          return m.exchange === this.exchange;
        }
        return true;
      });
    },
  },
});
