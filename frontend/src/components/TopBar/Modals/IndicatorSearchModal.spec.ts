import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchAvailableIndicators } from '@/api/indicatorClient';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import type { AvailableIndicator } from '@/types/contracts';

import IndicatorSearchModal from './IndicatorSearchModal.vue';

vi.mock('@/api/indicatorClient', () => ({
  fetchAvailableIndicators: vi.fn(),
  requestIndicator: vi.fn(),
}));

const sma: AvailableIndicator = {
  id: 3,
  name: 'SMA',
};

describe('IndicatorSearchModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(fetchAvailableIndicators).mockReset();
    vi.mocked(fetchAvailableIndicators).mockResolvedValue([sma]);
  });

  it('loads indicators through the typed client and requests indicators with market context', async () => {
    const currentMarketStore = useCurrentMarketStore();
    const currentTimeframeStore = useCurrentTimeframeStore();
    const indicatorsStore = useIndicatorsStore();
    currentMarketStore.setMarket({
      symbol_id: 1,
      symbol: 'EURUSD',
      exchange: 'FX',
      market_type: 'Forex',
      min_move: 0.00001,
      timezone: 'UTC',
    });
    currentTimeframeStore.setCurrentTimeframe({ label: 'M5', value: 'M5' });
    const requestIndicator = vi.spyOn(indicatorsStore, 'requestIndicator').mockResolvedValue('indicator-1');
    const wrapper = mount(IndicatorSearchModal, {
      global: {
        stubs: {
          BaseModal: { template: '<div><slot /></div>' },
          NIcon: true,
          NInput: true,
          NScrollbar: { template: '<div><slot /></div>' },
          SearchOutline: true,
          'base-modal': { template: '<div><slot /></div>' },
          'n-icon': true,
          'n-input': true,
          'n-scrollbar': { template: '<div><slot /></div>' },
          'search-outline': true,
        },
      },
    });
    await flushPromises();

    expect(fetchAvailableIndicators).toHaveBeenCalledOnce();

    (wrapper.vm as unknown as {
      onApplyIndicator: (indicator: AvailableIndicator) => void;
    }).onApplyIndicator(sma);

    expect(requestIndicator).toHaveBeenCalledWith(null, 3, {
      symbol: 'EURUSD',
      timeframe: 'M5',
      limit: 500,
      exchange: 'FX',
    }, {});
  });
});
