import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { deleteCandles } from '@/api/candleClient';
import { deleteMarket, fetchMarkets } from '@/api/marketClient';
import type { Market } from '@/types/contracts';

import RemoveMarketModal from '@/components/TopBar/Modals/RemoveMarketModal.vue';

vi.mock('@/api/candleClient', () => ({
  deleteCandles: vi.fn(),
}));

vi.mock('@/api/marketClient', () => ({
  deleteMarket: vi.fn(),
  fetchMarkets: vi.fn(),
}));

const market: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const BaseModalStub = defineComponent({
  name: 'BaseModal',
  setup(_, { expose, slots }) {
    expose({ close: vi.fn() });
    return () => h('div', [
      slots.default?.(),
      slots.footer?.(),
    ]);
  },
});

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      onClick: () => emit('click'),
    }, slots.default?.());
  },
});

function mountModal() {
  return mount(RemoveMarketModal, {
    props: { market },
    global: {
      stubs: {
        BaseModal: BaseModalStub,
        NButton: NButtonStub,
        NIcon: true,
        WarningOutline: true,
        'base-modal': BaseModalStub,
        'n-button': NButtonStub,
        'n-icon': true,
        'warning-outline': true,
      },
    },
  });
}

describe('RemoveMarketModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(deleteCandles).mockReset();
    vi.mocked(deleteCandles).mockResolvedValue({ status: 'deleted', deleted_count: 10 });
    vi.mocked(deleteMarket).mockReset();
    vi.mocked(deleteMarket).mockResolvedValue({ status: 'deleted', deleted_count: 1 });
    vi.mocked(fetchMarkets).mockReset();
    vi.mocked(fetchMarkets).mockResolvedValue([]);
  });

  it('deletes candle data through the typed client and emits market-removed', async () => {
    const wrapper = mountModal();

    await wrapper.findAll('.button-remove')[0].trigger('click');
    await flushPromises();

    expect(deleteCandles).toHaveBeenCalledWith('EURUSD', { exchange: 'FX' });
    expect(wrapper.emitted('market-removed')).toEqual([[market]]);
  });

  it('deletes a market through the typed client and refreshes markets', async () => {
    const wrapper = mountModal();

    await wrapper.findAll('.button-remove')[1].trigger('click');
    await flushPromises();

    expect(deleteMarket).toHaveBeenCalledWith('EURUSD', { exchange: 'FX' });
    expect(fetchMarkets).toHaveBeenCalledOnce();
    expect(wrapper.emitted('market-removed')).toBeUndefined();
  });
});
