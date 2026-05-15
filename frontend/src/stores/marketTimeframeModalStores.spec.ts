import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchMarkets } from '@/api/marketClient';
import {
  type Market,
  type TimeframeOption,
} from '@/types/contracts';
import { STORAGE_KEYS } from '@/utils/localStorage';

import { useCurrentMarketStore } from './currentMarketStore';
import { useCurrentTimeframeStore } from './currentTimeframeStore';
import { useMarketsStore } from './marketsStore';
import { useModalStore } from './modalStore';
import { useTimeframeStore } from './timeframeStore';

vi.mock('@/api/marketClient', () => ({
  fetchMarkets: vi.fn(),
}));

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

describe('market, timeframe, and modal stores', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.mocked(fetchMarkets).mockReset();
  });

  it('fetches markets through the typed client and stores the market list', async () => {
    vi.mocked(fetchMarkets).mockResolvedValue([marketA, marketB]);

    const store = useMarketsStore();
    await store.fetch();

    expect(fetchMarkets).toHaveBeenCalledOnce();
    expect(store.all).toEqual([marketA, marketB]);
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

  it('normalizes and persists the current timeframe', () => {
    localStorage.setItem(STORAGE_KEYS.CURRENT_TIMEFRAME, JSON.stringify({ value: 'h1' }));

    const store = useCurrentTimeframeStore();
    const nextTimeframe: TimeframeOption = { label: 'M5', value: 'M5' };

    expect(store.label).toBe('H1');
    expect(store.value).toBe('H1');

    store.setCurrentTimeframe(nextTimeframe);

    expect(store.label).toBe('M5');
    expect(store.value).toBe('M5');
    expect(JSON.parse(localStorage.getItem(STORAGE_KEYS.CURRENT_TIMEFRAME) ?? '{}')).toEqual(nextTimeframe);
  });

  it('keeps the legacy timeframe option API compatible', () => {
    const store = useTimeframeStore();

    expect(store.getCurrentTimeframe()).toEqual({ name: 'M1', value: 'M1' });

    store.setCurrentTimeframe({ name: 'H1', value: 'H1' });

    expect(store.currentTimeframe).toEqual({ name: 'H1', value: 'H1' });
    expect(store.getCurrentTimeframe()).toEqual({ name: 'H1', value: 'H1' });
  });

  it('tracks active modal state by name', () => {
    const store = useModalStore();

    expect(store.activeModal).toBeNull();
    expect(store.isModalOpen('symbolSearch')).toBe(false);

    store.openModal('symbolSearch');

    expect(store.activeModal).toBe('symbolSearch');
    expect(store.isModalOpen('symbolSearch')).toBe(true);
    expect(store.isModalOpen('indicatorSearch')).toBe(false);

    store.closeModal();

    expect(store.activeModal).toBeNull();
  });
});
