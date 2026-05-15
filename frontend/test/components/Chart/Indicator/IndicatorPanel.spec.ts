import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it } from 'vitest';

import IndicatorPanel from '@/components/Chart/Indicator/IndicatorPanel.vue';
import { useModalStore } from '@/stores/modalStore';
import type { StoreIndicator } from '@/stores/indicatorsStore';
import type { IndicatorInfo } from '@/types/contracts';

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

function createIndicator(overrides: Partial<StoreIndicator> = {}): StoreIndicator {
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
    ...overrides,
  };
}

describe('IndicatorPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
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
