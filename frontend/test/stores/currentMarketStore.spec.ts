import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import type { Market } from '@/types/contracts';
import { STORAGE_KEYS } from '@/utils/localStorage';

const marketA: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const marketB: Market = {
  symbol_id: 2,
  symbol: 'EURUSD',
  exchange: 'ALT',
  market_type: 'Forex',
  min_move: 0.0001,
  timezone: 'UTC',
};

describe('currentMarketStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('restores, persists, and validates current market by symbol and exchange', () => {
    localStorage.setItem(STORAGE_KEYS.CURRENT_MARKET, JSON.stringify(marketA));

    const store = useCurrentMarketStore();

    expect(store.symbol).toBe('EURUSD');
    expect(store.exchange).toBe('FX');
    expect(store.isValid([marketB])).toBe(false);
    expect(store.isValid([marketA, marketB])).toBe(true);

    store.setMarket(marketB);

    expect(store.exchange).toBe('ALT');
    expect(JSON.parse(localStorage.getItem(STORAGE_KEYS.CURRENT_MARKET) ?? '{}')).toEqual({
      exchange: 'ALT',
      market_type: 'Forex',
      min_move: 0.0001,
      symbol: 'EURUSD',
      symbol_id: 2,
    });
  });
});
