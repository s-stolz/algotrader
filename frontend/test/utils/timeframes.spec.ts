import { describe, expect, it } from 'vitest';

import {
  groupTimeframeOptions,
  normalizeTimeframeCode,
  timeframeToMinutes,
  TIMEFRAME_OPTIONS,
} from '@/utils/timeframes';

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

describe('groupTimeframeOptions', () => {
  it('groups and sorts caller-provided options by their complete units without changing the input', () => {
    const options = [
      { label: 'MN1', value: 'MN1' }, { label: 'H12', value: 'H12' },
      { label: 'M30', value: 'M30' }, { label: 'W1', value: 'W1' },
      { label: 'H1', value: 'H1' }, { label: 'M2', value: 'M2' },
    ] as const;
    const before = [...options];
    expect(groupTimeframeOptions(options)).toEqual([
      { label: 'Minutes', options: [options[5], options[2]] },
      { label: 'Hours', options: [options[4], options[1]] },
      { label: 'Weeks', options: [options[3]] },
      { label: 'Months', options: [options[0]] },
    ]);
    expect(options).toEqual(before);
  });

  it('omits empty groups and preserves exactly the selectable set', () => {
    expect(groupTimeframeOptions([])).toEqual([]);
    const groups = groupTimeframeOptions(TIMEFRAME_OPTIONS);
    expect(groups.map(group => group.label)).toEqual(['Minutes', 'Hours', 'Days']);
    expect(groups.flatMap(group => group.options)).toEqual(TIMEFRAME_OPTIONS);
  });
});
