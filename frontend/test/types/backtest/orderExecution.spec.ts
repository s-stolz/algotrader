import { describe, expect, it } from 'vitest';
import { isOrderExecution } from '@/types/backtest/orderExecution';

describe('saved order execution assumptions', () => {
  it('accepts legacy payloads and explicit order quotes', () => {
    expect(isOrderExecution({})).toBe(true);
    expect(
      isOrderExecution({
        execution_mode: 'orders',
        candle_quote: 'bid',
        spread: 0.01,
      }),
    ).toBe(true);
  });
  it('rejects missing quotes and invalid costs or position limits', () => {
    expect(isOrderExecution({ execution_mode: 'orders' })).toBe(false);
    expect(
      isOrderExecution({ execution_mode: 'orders', candle_quote: ['bid'] }),
    ).toBe(false);
    for (const spread of [-1, NaN, Infinity, '1']) {
      expect(
        isOrderExecution({
          execution_mode: 'orders',
          candle_quote: 'mid',
          spread,
        }),
      ).toBe(false);
    }
    expect(isOrderExecution({ max_position_quantity: 5 })).toBe(false);
  });
});
