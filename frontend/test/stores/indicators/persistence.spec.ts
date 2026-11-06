import { createPinia, setActivePinia, disposePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';
import { fetchAvailableIndicators } from '@/api/indicatorClient';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { IndicatorInfo } from '@/types/contracts';
import { STORAGE_KEYS } from '@/utils/localStorage';

vi.mock('@/api/indicatorClient', () => ({
  fetchAvailableIndicators: vi.fn(),
  requestIndicator: vi.fn(),
}));
vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn().mockResolvedValue(undefined) },
}));
const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: false,
  inputs: [],
  outputs: { sma: { type: 'line', plotOptions: { color: '#fff' } } },
  parameters: { window: { default: 20 } },
};

describe('persisted manual indicators', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.mocked(fetchAvailableIndicators)
      .mockReset()
      .mockResolvedValue([{ id: 9, indicator_id: 'sma', name: 'SMA' }]);
  });

  it('restores duplicate configurations and panes without runtime data', async () => {
    const store = useIndicatorsStore();
    await store.restorePersistedIndicators();
    const first = store.addIndicator(info, [{ timestamp_ms: 1000, sma: 3 }], 1);
    const second = store.addIndicator(info, [], 1);
    expect(first).not.toBe(second);
    store.updateIndicatorParameters(first, { window: 7 });
    store.getById(first)!.styles.sma = {
      color: '#f00',
      nested: { visible: false },
    };
    store.addIndicator(info, [], 1, {}, 'run-1');
    await nextTick();
    const saved = localStorage.getItem(STORAGE_KEYS.INDICATORS)!;
    expect(saved).not.toContain('timestamp_ms');
    expect(saved).not.toContain('run-1');
    setActivePinia(createPinia());
    const restored = useIndicatorsStore();
    await restored.restorePersistedIndicators();
    expect(restored.all).toHaveLength(2);
    expect(restored.all.map((item) => item.indicatorId)).toEqual([9, 9]);
    expect(restored.all.map((item) => item.paneIndex)).toEqual([1, 2]);
    expect(restored.paneCount).toBe(3);
    expect(restored.all[0].parameters.window.value).toBe(7);
    expect(restored.all[0].styles.sma).toEqual({
      color: '#f00',
      nested: { visible: false },
    });
    expect(restored.all[0].data).toEqual([]);
    restored.removeIndicator(restored.all[0]._id);
    await nextTick();
    expect(
      JSON.parse(localStorage.getItem(STORAGE_KEYS.INDICATORS)!).items,
    ).toHaveLength(1);
  });

  it('retains temporary failures and skips unavailable entries', async () => {
    const saved = { info, parameters: { window: 5 }, styles: {}, paneIndex: 1 };
    localStorage.setItem(
      STORAGE_KEYS.INDICATORS,
      JSON.stringify({ version: 1, items: [saved] }),
    );
    vi.mocked(fetchAvailableIndicators).mockRejectedValueOnce(
      new Error('offline'),
    );
    const pinia = createPinia();
    setActivePinia(pinia);
    await useIndicatorsStore().restorePersistedIndicators();
    await nextTick();
    expect(
      JSON.parse(localStorage.getItem(STORAGE_KEYS.INDICATORS)!).items,
    ).toEqual([saved]);
    disposePinia(pinia);
    localStorage.setItem(
      STORAGE_KEYS.INDICATORS,
      JSON.stringify({
        version: 1,
        items: [
          null,
          saved,
          { ...saved, info: { ...info, indicator_id: 'removed' } },
        ],
      }),
    );
    setActivePinia(createPinia());
    const restored = useIndicatorsStore();
    await restored.restorePersistedIndicators();
    await nextTick();
    expect(restored.all).toHaveLength(1);
    expect(
      JSON.parse(localStorage.getItem(STORAGE_KEYS.INDICATORS)!).items,
    ).toHaveLength(1);
  });
});
