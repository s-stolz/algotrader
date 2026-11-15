import { useMarketsStore } from '@/stores/marketsStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import type { Market } from '@/types/contracts';

export function seedBrokerMarket(overrides: Partial<Market> = {}): Market {
  const market: Market = {
    symbol_id: 1,
    symbol: 'EURUSD',
    exchange: 'FX',
    market_type: 'Forex',
    min_move: 0.00001,
    timezone: 'UTC',
    source_type: 'broker',
    broker_provider: 'ctrader',
    broker_account_id: '42',
    broker_environment: 'demo',
    broker_symbol_id: 99,
    ...overrides,
  };
  const store = useMarketsStore();
  store.all = [
    ...store.all.filter((item) => item.symbol_id !== market.symbol_id),
    market,
  ];
  useCurrentMarketStore().setMarket(market);
  return market;
}
