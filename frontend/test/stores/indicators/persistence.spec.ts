import { createPinia, setActivePinia, disposePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';
import {
  fetchAvailableIndicators,
  requestIndicator,
} from '@/api/indicatorClient';
import { wsService } from '@/utils/websocketService';
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
    vi.mocked(requestIndicator).mockReset();
    vi.mocked(wsService.send).mockClear();
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

  it.each([true, false])(
    'uses current live support (%s) after loading a saved indicator',
    async (supportsLive) => {
      const current: IndicatorInfo = {
        ...info,
        id: 5,
        indicator_id: 'currency_strength',
        name: 'Currency Strength',
        supports_live: supportsLive,
        outputs: { EUR: { type: 'line', plotOptions: { color: '#fff' } } },
        parameters: {},
      };
      localStorage.setItem(
        STORAGE_KEYS.INDICATORS,
        JSON.stringify({
          version: 1,
          items: [
            {
              info: { ...current, supports_live: !supportsLive },
              parameters: {},
              styles: { EUR: { color: '#f00', lineWidth: 3 } },
              paneIndex: 2,
            },
          ],
        }),
      );
      vi.mocked(fetchAvailableIndicators).mockResolvedValue([
        { id: 5, indicator_id: 'currency_strength', name: 'Currency Strength' },
      ]);
      vi.mocked(requestIndicator).mockResolvedValue({
        data: {
          indicator_info: current,
          indicator_data: [{ timestamp_ms: 1000, EUR: 1.5 }],
        },
      });
      const store = useIndicatorsStore();
      await store.restorePersistedIndicators();
      const restored = store.all[0];
      await store.requestIndicator(restored._id, 5, {
        symbol: 'EURUSD',
        timeframe: 'M1',
        exchange: 'FX',
      });
      expect(restored.info.supports_live).toBe(supportsLive);
      expect(store.liveSubscriptions.has(restored._id)).toBe(supportsLive);
      expect(wsService.send).toHaveBeenCalledTimes(supportsLive ? 1 : 0);
      expect(restored.styles).toEqual({ EUR: { color: '#f00', lineWidth: 3 } });
      expect(restored.paneIndex).toBe(2);
      expect(restored.data).toEqual([{ timestamp_ms: 1000, EUR: 1.5 }]);
      await nextTick();
      expect(
        JSON.parse(localStorage.getItem(STORAGE_KEYS.INDICATORS)!).items[0].info
          .supports_live,
      ).toBe(supportsLive);
    },
  );

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
