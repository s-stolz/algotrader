import { defineStore } from 'pinia';
import { ref } from 'vue';

import {
  isStoredCurrentMarket,
  type Market,
  type StoredCurrentMarket,
} from '@/types/contracts';
import { getStoredState, setStoredState, STORAGE_KEYS } from '@/utils/localStorage';

type CurrentMarketInput = Market | StoredCurrentMarket;

const emptyMarket: StoredCurrentMarket = {
  exchange: null,
  market_type: null,
  min_move: null,
  symbol: null,
  symbol_id: null,
};

function readStoredMarket(): StoredCurrentMarket {
  const stored = getStoredState<unknown>(STORAGE_KEYS.CURRENT_MARKET);

  if (isStoredCurrentMarket(stored)) {
    return stored;
  }

  return emptyMarket;
}

export const useCurrentMarketStore = defineStore('currentMarket', () => {
  const stored = readStoredMarket();
  const exchange = ref<string | null>(stored.exchange);
  const market_type = ref<string | null>(stored.market_type);
  const min_move = ref<number | null>(stored.min_move);
  const symbol = ref<string | null>(stored.symbol);
  const symbol_id = ref<number | null>(stored.symbol_id);

  function snapshot(): StoredCurrentMarket {
    return {
      exchange: exchange.value,
      market_type: market_type.value,
      min_move: min_move.value,
      symbol: symbol.value,
      symbol_id: symbol_id.value,
    };
  }

  function setMarket(market: CurrentMarketInput): void {
    exchange.value = market.exchange;
    market_type.value = market.market_type;
    min_move.value = market.min_move;
    symbol.value = market.symbol;
    symbol_id.value = market.symbol_id;

    setStoredState(STORAGE_KEYS.CURRENT_MARKET, snapshot());
  }

  function isValid(availableMarkets: Market[]): boolean {
    if (!symbol.value) return false;

    return availableMarkets.some((market) => {
      if (market.symbol !== symbol.value) return false;
      if (exchange.value) {
        return market.exchange === exchange.value;
      }
      return true;
    });
  }

  return {
    exchange,
    market_type,
    min_move,
    symbol,
    symbol_id,
    setMarket,
    isValid,
  };
});
