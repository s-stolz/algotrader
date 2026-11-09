import { describe, expect, it } from 'vitest';
import { matchesBacktestMarket } from '@/utils/backtestMarket';

const market = {
  symbol_id: 1,
  symbol: 'RENAMED',
  exchange: 'NEW',
  aliases: [{ symbol: 'EURUSD', exchange: 'FX' }],
};
const request = { symbols: ['EURUSD'], exchange: 'FX' };

describe('saved backtest market identity', () => {
  it('matches current names and historical aliases with the requested exchange', () => {
    expect(matchesBacktestMarket(market, request, 'exact')).toBe(true);
    expect(
      matchesBacktestMarket(
        market,
        { symbols: ['RENAMED'], exchange: 'NEW' },
        'exact',
      ),
    ).toBe(true);
    expect(
      matchesBacktestMarket(market, { ...request, exchange: 'OTHER' }, 'exact'),
    ).toBe(false);
  });
  it('lets callers choose whether an unspecified exchange can match', () => {
    expect(
      matchesBacktestMarket(market, { ...request, exchange: null }, 'exact'),
    ).toBe(false);
    expect(
      matchesBacktestMarket(
        market,
        { ...request, exchange: null },
        'allow-unspecified',
      ),
    ).toBe(true);
  });
  it('uses a saved stable ID without falling back to matching names', () => {
    const instrument = {
      symbol_id: 1,
      settlement_currency: 'USD',
      contract_multiplier: 1,
      minimum_quantity: 1,
      quantity_step: 1,
      min_move: 0.01,
    };
    expect(
      matchesBacktestMarket(market, { ...request, instrument }, 'exact'),
    ).toBe(true);
    expect(
      matchesBacktestMarket(
        market,
        { ...request, instrument: { ...instrument, symbol_id: 2 } },
        'exact',
      ),
    ).toBe(false);
  });
});
