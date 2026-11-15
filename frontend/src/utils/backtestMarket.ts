import type { BacktestRequestPayload } from '@/types/backtest/requests';

export interface MarketIdentity {
  symbol_id: number | null;
  symbol: string | null;
  exchange: string | null;
}

export function matchesBacktestMarket(
  market: MarketIdentity,
  request: Pick<BacktestRequestPayload, 'instrument' | 'symbols' | 'exchange'>,
  exchangePolicy: 'exact' | 'allow-unspecified',
): boolean {
  if (request.instrument)
    return market.symbol_id === request.instrument.symbol_id;
  const matchesName = (name: Pick<MarketIdentity, 'symbol' | 'exchange'>) =>
    name.symbol === request.symbols[0] &&
    (name.exchange === request.exchange ||
      (exchangePolicy === 'allow-unspecified' && !request.exchange));
  return matchesName(market);
}
