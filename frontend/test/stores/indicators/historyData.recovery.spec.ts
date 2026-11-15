import { expect, it } from 'vitest';
import { mergeRecoveredIndicatorData } from '@/stores/indicators/historyData';

it('merges history and live fields in order without mutating inputs', () => {
  const existing = Object.freeze([
    Object.freeze({ timestamp_ms: 1000, mid: 1 }),
    Object.freeze({ timestamp_ms: 2000, mid: 2 }),
  ]);
  const recovered = Object.freeze([
    Object.freeze({ timestamp_ms: 3000, mid: 3, upper: 4 }),
    Object.freeze({ timestamp_ms: 2000, mid: 2.5 }),
  ]);
  const live = Object.freeze([
    Object.freeze({ timestamp_ms: 4000, mid: 5 }),
    Object.freeze({ timestamp_ms: 3000, mid: 3.5 }),
  ]);
  expect(mergeRecoveredIndicatorData(existing, recovered, live)).toEqual([
    { timestamp_ms: 1000, mid: 1 },
    { timestamp_ms: 2000, mid: 2.5 },
    { timestamp_ms: 3000, mid: 3.5, upper: 4 },
    { timestamp_ms: 4000, mid: 5 },
  ]);
});
