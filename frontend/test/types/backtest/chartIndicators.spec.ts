import { describe, expect, it } from 'vitest';
import { readChartIndicators } from '@/types/backtest/chartIndicators';

describe('saved chart indicator contract', () => {
  it('distinguishes absent legacy metadata from an explicitly empty group', () => {
    expect(readChartIndicators(null)).toBeNull();
    expect(
      readChartIndicators({
        chart_indicators: { schema_version: 1, items: [] },
      }),
    ).toEqual([]);
  });
  it('rejects malformed items without affecting legacy run parsing', () => {
    expect(() =>
      readChartIndicators({
        chart_indicators: {
          schema_version: 1,
          items: [{ indicator_id: 'sma', parameters: null }],
        },
      }),
    ).toThrow('invalid');
  });
});
