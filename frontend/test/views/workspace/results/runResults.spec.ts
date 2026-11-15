import { describe, it, expect } from 'vitest';
import {
  summarizeTrades,
  periodProfit,
  compareResultValues,
  formatResult,
} from '@/views/workspace/results/runResults';
import { resultRun, resultTrade } from './resultFixtures';
describe('run trade results', () => {
  it('uses net P&L once, includes breakevens and measures elapsed holding time', () => {
    const result = summarizeTrades(
      [resultTrade(120), resultTrade(-40), resultTrade(0)],
      3,
    );
    expect(result.metrics).toMatchObject({
      'net-profit': 80,
      'profit-factor': 3,
      expectancy: 80 / 3,
      'holding-time': 2,
    });
    expect(result.metrics['win-rate']).toBeCloseTo(100 / 3);
  });
  it('distinguishes no trades, no losses, and all breakevens', () => {
    expect(summarizeTrades([], null).metrics).toMatchObject({
      'net-profit': 0,
      'win-rate': null,
      'profit-factor': null,
    });
    expect(
      summarizeTrades([resultTrade(10)], Infinity).metrics['profit-factor'],
    ).toBe(Infinity);
    expect(
      summarizeTrades([resultTrade(0)], null).metrics['profit-factor'],
    ).toBeNull();
    expect(formatResult(Infinity, 'ratio')).toBe('∞');
  });
  it('groups by UTC exit month and excludes the end boundary from coverage', () => {
    const result = summarizeTrades(
      [
        resultTrade(100, Date.UTC(2024, 11, 31, 23, 59)),
        resultTrade(-30, Date.UTC(2025, 0, 1)),
      ],
      100 / 30,
    );
    const run = resultRun('run', Date.UTC(2024, 11, 15), Date.UTC(2025, 2));
    expect(periodProfit(run, result, 2024)).toBe(100);
    expect(periodProfit(run, result, 2025)).toBe(-30);
    expect(periodProfit(run, result, 2025, 1)).toBe(0);
    expect(periodProfit(run, result, 2025, 2)).toBeNull();
    expect(periodProfit(run, undefined, 2025, 0)).toBeNull();
  });
  it('sorts raw numbers, infinity and missing values in both directions', () => {
    const values = [null, 2.004, -5, Infinity, 2.001, null];
    expect(
      [...values].sort((a, b) => compareResultValues(a, b, 'ascend')),
    ).toEqual([-5, 2.001, 2.004, Infinity, null, null]);
    expect(
      [...values].sort((a, b) => compareResultValues(a, b, 'descend')),
    ).toEqual([Infinity, 2.004, 2.001, -5, null, null]);
    expect(compareResultValues(Infinity, Infinity, 'ascend')).toBe(0);
  });
});
