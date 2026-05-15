import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchMarkets } from '@/api/marketClient';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import type { Market } from '@/types/contracts';

import ChartView from './ChartView.vue';

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

describe('ChartView startup', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.mocked(fetchMarkets).mockReset();
  });

  it('fetches markets and initializes the current market when persisted state is invalid', async () => {
    vi.mocked(fetchMarkets).mockResolvedValue([marketA]);
    const currentMarketStore = useCurrentMarketStore();
    currentMarketStore.setMarket(marketB);

    mount(ChartView, {
      global: {
        stubs: {
          ChartArea: true,
          TheTopBar: true,
          'chart-area': true,
          'the-top-bar': true,
        },
      },
    });
    await flushPromises();

    expect(fetchMarkets).toHaveBeenCalledOnce();
    expect(currentMarketStore.symbol).toBe('EURUSD');
    expect(currentMarketStore.exchange).toBe('FX');
    expect(currentMarketStore.symbol_id).toBe(1);
  });
});
