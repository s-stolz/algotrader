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
    return () =>
      h(
        'button',
        {
          ...attrs,
          onClick: () => emit('click'),
        },
        [slots.icon?.(), slots.default?.()],
      );
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
    const marketButton = wrapper
      .findAll('button')
      .find((button) => button.text() === 'EURUSD');
    expect(marketButton).toBeDefined();
    await marketButton!.trigger('click');
    expect(openModal).toHaveBeenCalledWith('symbolSearch');
    wrapper.unmount();
  });
  it('preserves focus and mode identity with themed circular controls', async () => {
    const wrapper = mount(TheTopBar, {
      attachTo: document.body,
      global: { stubs: { TimeframeDropdown: true, TopBarModals: true } },
    });
    const pan = wrapper.get('button[aria-label="Pan mode"]');
    const measure = wrapper.get('button[aria-label="Measure mode"]');
    expect(pan.attributes('aria-pressed')).toBe('true');
    expect(measure.attributes('aria-pressed')).toBe('false');
    (measure.element as HTMLElement).focus();
    await measure.trigger('click');
    expect(wrapper.emitted('update:chartInteractionMode')).toEqual([
      ['measure'],
    ]);
    await wrapper.setProps({ chartInteractionMode: 'measure' });
    expect(measure.attributes('aria-pressed')).toBe('true');
    expect(document.activeElement).toBe(measure.element);
    wrapper.unmount();
  });
});
