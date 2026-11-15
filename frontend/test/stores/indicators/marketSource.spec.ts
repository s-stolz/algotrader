import { beforeEach, expect, it } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import {
  findLiveMarket,
  matchesCurrentBrokerMarket,
} from '@/stores/indicators/marketSource';
import { useMarketsStore } from '@/stores/marketsStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { seedBrokerMarket } from '../../fixtures/brokerMarket';

beforeEach(() => setActivePinia(createPinia()));
it('excludes custom instruments and ambiguous broker symbol matches', () => {
  const broker = seedBrokerMarket();
  const custom = {
    ...broker,
    symbol_id: 2,
    source_type: 'custom' as const,
    exchange: 'CSV',
  };
  useMarketsStore().all.push(custom);
  expect(findLiveMarket('EURUSD', 'CSV')).toBeNull();
  expect(findLiveMarket('EURUSD', null)?.symbol_id).toBe(1);
  useMarketsStore().all.push({ ...broker, symbol_id: 3, exchange: 'SECOND' });
  expect(findLiveMarket('EURUSD', null)).toBeNull();
  expect(findLiveMarket('EURUSD', 'FX')?.symbol_id).toBe(1);
  useCurrentMarketStore().setMarket(custom);
  expect(matchesCurrentBrokerMarket(1)).toBe(false);
});
