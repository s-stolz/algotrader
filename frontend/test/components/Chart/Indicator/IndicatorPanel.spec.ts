import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import IndicatorPanel from '@/components/Chart/Indicator/IndicatorPanel.vue';
import { useModalStore } from '@/stores/modalStore';
import type { StoreIndicator } from '@/stores/indicatorsStore';
import type { IndicatorInfo } from '@/types/contracts';

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
        slots.default?.(),
      );
  },
});

const indicatorInfo: IndicatorInfo = {
  id: 7,
  indicator_id: 'sma',
  name: 'SMA',
  overlay: false,
  inputs: [],
  outputs: {
    timestamp: { type: 'time' },
    sma: {
      type: 'line',
      plotOptions: {
        color: '#3366ff',
        lineWidth: 2,
        priceFormat: {
          precision: 2,
          minMove: 0.01,
        },
      },
    },
  },
  parameters: {
    length: {
      type: 'int',
      default: 14,
      min: 1,
      max: 200,
      step: 1,
    },
    source: {
      type: 'string',
      default: 'close',
      options: ['open', 'close'],
    },
  },
};

function createIndicator(
  overrides: Partial<StoreIndicator> = {},
): StoreIndicator {
  return {
    _id: 'indicator-1',
    indicatorId: 7,
    info: indicatorInfo,
    paneIndex: 1,
    paneHtmlElement: null,
    data: [{ timestamp_ms: 1_700_000_000_000, sma: 1.23 }],
    lastLivePoint: null,
    dataVersion: 0,
    parameters: {
      length: {
        type: 'int',
        value: 14,
        default: 14,
        min: 1,
        max: 200,
        step: 1,
      },
      source: {
        type: 'string',
        value: 'close',
        default: 'close',
        options: ['open', 'close'],
      },
    },
    styles: {
      sma: { color: '#3366ff', lineWidth: 2 },
    },
    currentLimit: 500,
    hasExpandedHistory: false,
    historyGeneration: 0,
    isBackfilling: false,
    historyExhausted: false,
    targetOldestTimestampMs: null,
    targetNewestTimestampMs: null,
    nextBackfillEndMs: null,
    activeBackfillPromise: null,
    ...overrides,
  };
}

describe('IndicatorPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it.each(['sma', 'rsi', 'macd'])(
    'does not show no-data help for %s while its data is empty',
    (indicatorId) => {
      const wrapper = mount(IndicatorPanel, {
        props: {
          indicator: createIndicator({
            info: { ...indicatorInfo, indicator_id: indicatorId },
            data: [],
          }),
        },
        global: { stubs: { NButton: NButtonStub, NIcon: true } },
      });
      expect(wrapper.find('.indicator-empty-state').exists()).toBe(false);
      wrapper.unmount();
    },
  );

  it.each([{ data: [] }, { data: [{ timestamp_ms: 1000, sma: null }] }])(
    'shows empty-state help after the remove control when no values can be plotted',
    async ({ data }) => {
      const indicator = createIndicator({
        info: { ...indicatorInfo, indicator_id: 'currency_strength' },
        data,
      });
      const wrapper = mount(IndicatorPanel, {
        props: { indicator },
        global: { stubs: { NButton: NButtonStub, NIcon: true } },
      });
      const message = 'No data available for this symbol and indicator.';
      const help = wrapper.get('.indicator-empty-state');
      expect(
        wrapper
          .get('.indicator-controls')
          .findAll('button')
          .map((button) => button.attributes('aria-label')),
      ).toEqual(['Indicator settings', 'Remove Indicator', message]);
      expect(wrapper.text()).not.toContain(message);
      expect(document.querySelector('.base-popover')).toBeNull();
      await help.trigger('mouseenter');
      await vi.waitFor(() => {
        expect(document.querySelector('.base-popover')?.textContent).toContain(
          message,
        );
      });
      await help.trigger('mouseleave');
      await wrapper.get('[aria-label="Indicator settings"]').trigger('click');
      expect(useModalStore().activeModal).toBe('indicatorSettings_indicator-1');
      await wrapper.get('[aria-label="Remove Indicator"]').trigger('click');
      expect(wrapper.emitted('remove-indicator')).toEqual([['indicator-1']]);

      await wrapper.setProps({
        indicator: { ...indicator, data: createIndicator().data },
      });
      expect(wrapper.find('.indicator-empty-state').exists()).toBe(false);
      await wrapper.setProps({ indicator });
      expect(wrapper.find('.indicator-empty-state').exists()).toBe(true);
      await wrapper.setProps({
        indicator: {
          ...indicator,
          lastLivePoint: { timestamp_ms: 2000, sma: 0 },
        },
      });
      expect(wrapper.find('.indicator-empty-state').exists()).toBe(false);
      wrapper.unmount();
    },
  );

  it('omits the historical suffix for live currency strength', async () => {
    const indicator = createIndicator({
      info: {
        ...indicatorInfo,
        name: 'Currency Strength',
        supports_live: true,
      },
    });
    const wrapper = mount(IndicatorPanel, {
      props: { indicator },
      global: { stubs: { NButton: true, NIcon: true } },
    });
    expect(wrapper.text()).toBe('Currency Strength');
    await wrapper.setProps({
      indicator: {
        ...indicator,
        info: { ...indicator.info, supports_live: false },
      },
    });
    expect(wrapper.text()).toContain('Historical');
  });

  it('opens settings from the panel and emits removal with the indicator id', async () => {
    const modalStore = useModalStore();
    expect(modalStore.activeModal).toBeNull();

    const wrapper = mount(IndicatorPanel, {
      props: {
        indicator: createIndicator(),
      },
      global: {
        stubs: {
          NButton: NButtonStub,
          NIcon: true,
          SettingsOutline: true,
          TrashOutline: true,
          'n-button': NButtonStub,
          'n-icon': true,
          'settings-outline': true,
          'trash-outline': true,
        },
      },
    });

    const buttons = wrapper.findAll('button');
    await buttons[0].trigger('click');

    expect(modalStore.activeModal).toBe('indicatorSettings_indicator-1');

    await buttons[1].trigger('click');

    expect(wrapper.emitted('remove-indicator')).toEqual([['indicator-1']]);
  });
});
