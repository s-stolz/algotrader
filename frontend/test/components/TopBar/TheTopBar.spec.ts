import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useModalStore } from '@/stores/modalStore';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';

import TheTopBar from '@/components/TopBar/TheTopBar.vue';

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      onClick: () => emit('click'),
    }, [
      slots.icon?.(),
      slots.default?.(),
    ]);
  },
});

describe('TheTopBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('shows the selected market and opens market search', async () => {
    useCurrentMarketStore().setMarket({
      symbol_id: 1,
      symbol: 'EURUSD',
      exchange: 'FX',
      market_type: 'Forex',
      min_move: 0.00001,
      timezone: 'UTC',
    });

    const wrapper = mount(TheTopBar, {
      global: {
        stubs: {
          NButton: NButtonStub,
          NIcon: true,
          TimeframeDropdown: true,
          TopBarModals: true,
          'n-button': NButtonStub,
          'n-icon': true,
          'timeframe-dropdown': true,
          'top-bar-modals': true,
        },
      },
    });

    const openModal = vi.spyOn(useModalStore(), 'openModal');
    const marketButton = wrapper.findAll('button').find((button) => button.text() === 'EURUSD');
    expect(marketButton).toBeDefined();
    await marketButton!.trigger('click');
    expect(openModal).toHaveBeenCalledWith('symbolSearch');
    wrapper.unmount();
  });
});
