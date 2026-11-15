import { useMarketsStore } from '../marketsStore';
import { useCurrentMarketStore } from '../currentMarketStore';

export function findLiveMarket(symbol: string, exchange: string | null) {
  const matches = useMarketsStore().all.filter(
    (market) =>
      market.source_type === 'broker' &&
      market.symbol === symbol &&
      (!exchange || market.exchange === exchange),
  );
  return matches.length === 1 ? matches[0] : null;
}

export function matchesCurrentBrokerMarket(marketId: number): boolean {
  const current = useCurrentMarketStore();
  return current.source_type === 'broker' && current.symbol_id === marketId;
}
