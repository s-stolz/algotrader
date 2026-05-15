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

  it('normalizes and persists the current timeframe', () => {
    localStorage.setItem(STORAGE_KEYS.CURRENT_TIMEFRAME, JSON.stringify({ value: 'h1' }));

    const store = useCurrentTimeframeStore();
    const nextTimeframe: TimeframeOption = { label: 'M5', value: 'M5' };

    expect(store.label).toBe('H1');
    expect(store.value).toBe('H1');

    store.setCurrentTimeframe(nextTimeframe);

    expect(store.label).toBe('M5');
    expect(store.value).toBe('M5');
    expect(JSON.parse(localStorage.getItem(STORAGE_KEYS.CURRENT_TIMEFRAME) ?? '{}')).toEqual(nextTimeframe);
  });
});
