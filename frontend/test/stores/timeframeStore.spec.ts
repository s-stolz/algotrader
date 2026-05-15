import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useTimeframeStore } from '@/stores/timeframeStore';

describe('timeframeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('keeps the legacy timeframe option API compatible', () => {
    const store = useTimeframeStore();

    expect(store.getCurrentTimeframe()).toEqual({ name: 'M1', value: 'M1' });

    store.setCurrentTimeframe({ name: 'H1', value: 'H1' });

    expect(store.currentTimeframe).toEqual({ name: 'H1', value: 'H1' });
    expect(store.getCurrentTimeframe()).toEqual({ name: 'H1', value: 'H1' });
  });
});
