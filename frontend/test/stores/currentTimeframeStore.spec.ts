import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import type { TimeframeOption } from '@/types/contracts';
import { STORAGE_KEYS } from '@/utils/localStorage';

describe('currentTimeframeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it('loads and persists the current timeframe', () => {
    localStorage.setItem(
      STORAGE_KEYS.CURRENT_TIMEFRAME,
      JSON.stringify({ label: 'H1', value: 'H1' }),
    );

    const store = useCurrentTimeframeStore();
    const nextTimeframe: TimeframeOption = { label: 'M5', value: 'M5' };

    expect(store.label).toBe('H1');
    expect(store.value).toBe('H1');

    store.setCurrentTimeframe(nextTimeframe);

    expect(store.label).toBe('M5');
    expect(store.value).toBe('M5');
    expect(
      JSON.parse(localStorage.getItem(STORAGE_KEYS.CURRENT_TIMEFRAME) ?? '{}'),
    ).toEqual(nextTimeframe);
  });

  it.each([null, {}, { value: 60 }, { value: 'h1' }])(
    'falls back safely for invalid stored preferences: %j',
    (stored) => {
      localStorage.setItem(
        STORAGE_KEYS.CURRENT_TIMEFRAME,
        JSON.stringify(stored),
      );
      const store = useCurrentTimeframeStore();
      expect(store.value).toBe('M1');
    },
  );
});
