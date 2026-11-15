import { describe, expect, it } from 'vitest';
import { buildRangeBoxes, rangeStyle } from '@/utils/chart/openingRange/model';

const point = {
  timestamp_ms: 2000,
  range_start_ms: 1000,
  range_end_ms: 3000,
  extension_end_ms: 5000,
  range_high: 12,
  range_low: 8,
  ready: 0,
};

describe('opening range geometry', () => {
  it('uses the latest causal bounds and keeps sessions separate after paging', () => {
    expect(
      buildRangeBoxes([
        { ...point, timestamp_ms: 4000, ready: 1 },
        point,
        {
          ...point,
          timestamp_ms: 12000,
          range_start_ms: 11000,
          range_end_ms: 13000,
          extension_end_ms: 15000,
          range_high: 20,
        },
      ]),
    ).toEqual([
      { start: 1, end: 3, extensionEnd: 5, high: 12, low: 8, ready: true },
      { start: 11, end: 12, extensionEnd: 15, high: 20, low: 8, ready: false },
    ]);
  });

  it('omits pre-session placeholders and invalid values', () => {
    expect(
      buildRangeBoxes([
        { ...point, timestamp_ms: 0, range_high: 0, range_low: 0 },
        { ...point, range_high: null },
        { ...point, range_low: NaN },
        { ...point, range_high: 7 },
      ]),
    ).toEqual([]);
  });

  it('accepts equal high and low and independently hides extensions', () => {
    expect(buildRangeBoxes([{ ...point, range_high: 8 }])).toHaveLength(1);
    expect(rangeStyle({ showExtensions: false }).showExtensions).toBe(false);
    expect(rangeStyle().showExtensions).toBe(true);
  });
});
