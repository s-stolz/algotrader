import { describe, expect, it } from 'vitest';
import { isBacktestRequestPayload } from '@/types/backtest/requests';
import { isBacktestMarket } from '@/types/backtest/definitions';
import { initialDraft } from '@/views/creation/creationRequest';

describe('saved market price increment', () => {
  it('accepts legacy requests and positive saved increments', () => {
    const request = initialDraft();
    request.symbols = ['TEST'];
    request.strategy.strategy_id = 'rsi_range_limit';
    expect(isBacktestRequestPayload(request)).toBe(true);
    for (const value of [0.00001, 0.25]) {
      expect(
        isBacktestRequestPayload({ ...request, market_min_move: value }),
      ).toBe(true);
      expect(
        isBacktestMarket({
          symbol_id: 1,
          symbol: 'TEST',
          exchange: 'FX',
          min_move: value,
        }),
      ).toBe(true);
    }
    for (const value of [0, -1, NaN, Infinity, true, '0.01']) {
      expect(
        isBacktestRequestPayload({ ...request, market_min_move: value }),
      ).toBe(false);
      expect(
        isBacktestMarket({
          symbol_id: 1,
          symbol: 'TEST',
          exchange: 'FX',
          min_move: value,
        }),
      ).toBe(false);
    }
  });
});
