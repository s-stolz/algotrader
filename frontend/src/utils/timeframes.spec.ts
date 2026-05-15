import { describe, expect, it } from 'vitest';

import {
  normalizeTimeframeCode,
  timeframeToMinutes,
  TIMEFRAME_OPTIONS,
} from './timeframes';

describe('timeframe utilities', () => {
  it('normalizes known string and numeric timeframe values', () => {
    expect(normalizeTimeframeCode('m5')).toBe('M5');
    expect(normalizeTimeframeCode('H1')).toBe('H1');
    expect(normalizeTimeframeCode(60)).toBe('H1');
    expect(normalizeTimeframeCode(43200)).toBe('MN1');
  });

  it('falls back to M1 for unsupported inputs', () => {
    expect(normalizeTimeframeCode('bad')).toBe('M1');
    expect(normalizeTimeframeCode(7)).toBe('M1');
    expect(timeframeToMinutes('bad')).toBe(1);
  });

  it('keeps selectable UI options stable', () => {
    expect(TIMEFRAME_OPTIONS).toEqual([
      { label: 'M1', value: 'M1' },
      { label: 'M5', value: 'M5' },
      { label: 'M15', value: 'M15' },
      { label: 'M30', value: 'M30' },
      { label: 'H1', value: 'H1' },
      { label: 'H4', value: 'H4' },
      { label: 'D1', value: 'D1' },
    ]);
  });
});
