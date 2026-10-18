import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchMarkets } from '@/api/marketClient';
import { useMarketsStore } from '@/stores/marketsStore';
import type { Market } from '@/types/contracts';

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

describe('marketsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(fetchMarkets).mockReset();
  });

  it('fetches markets through the typed client and stores the market list', async () => {
    vi.mocked(fetchMarkets).mockResolvedValue([marketA, marketB]);

    const store = useMarketsStore();
    await store.fetch();

    expect(fetchMarkets).toHaveBeenCalledOnce();
    expect(store.all).toEqual([marketA, marketB]);
  });
});
