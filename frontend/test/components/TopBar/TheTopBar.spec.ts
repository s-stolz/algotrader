import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it } from 'vitest';

import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useModalStore } from '@/stores/modalStore';

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

  it('opens Backtests from the chart header', async () => {
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

    expect(wrapper.find('[data-testid="open-backtest-runs"]').text()).toBe('Backtests');
    expect(wrapper.find('[data-testid="open-backtest-runs"] n-icon-stub').exists()).toBe(false);

    await wrapper.find('[data-testid="open-backtest-runs"]').trigger('click');

    expect(useModalStore().activeModal).toBe('backtestRuns');
  });
});
