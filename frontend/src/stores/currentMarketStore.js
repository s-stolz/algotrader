import { defineStore } from "pinia";

export const useCurrentMarketStore = defineStore('currentMarket', {
  state: () => ({
    exchange: null,
    market_type: null,
    min_move: null,
    symbol: null,
    symbol_id: null
  }),
  actions: {
    setMarket(market) {
      Object.assign(this, market);
    },
  },
});
