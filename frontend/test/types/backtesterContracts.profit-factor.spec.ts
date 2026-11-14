import { describe, it, expect } from 'vitest';
import { isBacktestRun } from '@/types/backtesterContracts';
import { decodeProfitFactor } from '@/types/backtest/results';
import { backtestRun } from '../api/backtesterClient.fixtures';

describe('saved profit factor', () => {
  it.each([0, 2.5, 'infinity', null])(
    'preserves %s through JSON and decodes it',
    (value) => {
      const run = backtestRun();
      const payload = JSON.parse(
        JSON.stringify({ ...run, metrics: { profit_factor: value } }),
      );
      expect(isBacktestRun(payload)).toBe(true);
      expect(decodeProfitFactor(payload.metrics.profit_factor)).toBe(
        value === 'infinity' ? Infinity : value,
      );
    },
  );
  it.each([
    undefined,
    true,
    false,
    -1,
    NaN,
    Infinity,
    -Infinity,
    '2',
    'Infinity',
    {},
    [],
  ])('rejects invalid or missing %s', (value) => {
    expect(
      isBacktestRun({ ...backtestRun(), metrics: { profit_factor: value } }),
    ).toBe(false);
    expect(() => decodeProfitFactor(value)).toThrow(
      'Invalid saved profit factor',
    );
  });
  it('rejects missing successful metrics but allows non-success without them', () => {
    expect(isBacktestRun({ ...backtestRun(), metrics: null })).toBe(false);
    expect(isBacktestRun({ ...backtestRun(), metrics: {} })).toBe(false);
    expect(
      isBacktestRun({ ...backtestRun(), status: 'failed', metrics: null }),
    ).toBe(true);
  });
});
