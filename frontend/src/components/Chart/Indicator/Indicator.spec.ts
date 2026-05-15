import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { useIndicatorsStore, type StoreIndicator } from '@/stores/indicatorsStore';
import { useModalStore } from '@/stores/modalStore';
import type { IndicatorInfo, JsonObject } from '@/types/contracts';

import Indicator from './Indicator.vue';
import IndicatorPanel from './IndicatorPanel.vue';
import IndicatorSettingsParameters from './IndicatorSettingsParameters.vue';
import IndicatorSettingsStyles from './IndicatorSettingsStyles.vue';

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

const SlotStub = defineComponent({
  name: 'SlotStub',
  setup(_, { slots }) {
    return () => h('div', slots.default?.());
  },
});

const NInputNumberStub = defineComponent({
  name: 'NInputNumber',
  props: {
    value: {
      type: Number,
      default: null,
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      type: 'number',
      value: props.value ?? '',
      onInput: (event: Event) => {
        const input = event.target as HTMLInputElement;
        emit('update:value', input.value === '' ? null : Number(input.value));
      },
    });
  },
});

const NInputStub = defineComponent({
  name: 'NInput',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      type: 'text',
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    });
  },
});

const NColorPickerStub = defineComponent({
  name: 'NColorPicker',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => h('input', {
      class: 'color-picker',
      type: 'color',
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    });
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

describe('indicator components', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
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

  it('delegates wrapper removal, style updates, and data refreshes to the indicator manager seam', async () => {
    const pane = document.createElement('div');
    const wrapperTarget = document.createElement('div');
    wrapperTarget.className = 'indicators-wrapper';
    pane.appendChild(wrapperTarget);
    document.body.appendChild(pane);

    const manager = {
      addIndicatorSeries: vi.fn().mockResolvedValue(undefined),
      refreshIndicatorSeries: vi.fn(),
      removeIndicatorSeriesAndData: vi.fn(),
      updateMissingPaneHtmlElements: vi.fn().mockResolvedValue(undefined),
      updateIndicatorStyles: vi.fn().mockReturnValue(true),
    };
    const indicator = createIndicator({ paneHtmlElement: pane });

    const wrapper = mount(Indicator, {
      props: {
        indicator,
        indicatorManager: manager,
      },
      global: {
        stubs: {
          teleport: true,
          IndicatorPanel: defineComponent({
            name: 'IndicatorPanel',
            emits: ['remove-indicator'],
            setup(_, { emit }) {
              return () => h('button', {
                class: 'remove-indicator',
                onClick: () => emit('remove-indicator', 'indicator-1'),
              });
            },
          }),
          IndicatorSettingsModal: defineComponent({
            name: 'IndicatorSettingsModal',
            emits: ['update-styles'],
            setup(_, { emit }) {
              return () => h('button', {
                class: 'update-styles',
                onClick: () => emit('update-styles', {
                  outputKey: 'sma',
                  styles: { color: '#ff0000' },
                }),
              });
            },
          }),
        },
      },
      attachTo: document.body,
    });

    expect(manager.addIndicatorSeries).toHaveBeenCalledWith('indicator-1');

    await wrapper.find('.update-styles').trigger('click');
    expect(manager.updateIndicatorStyles).toHaveBeenCalledWith('indicator-1', 'sma', {
      color: '#ff0000',
    });

    await wrapper.setProps({
      indicator: createIndicator({ paneHtmlElement: pane, dataVersion: 1 }),
    });
    expect(manager.refreshIndicatorSeries).toHaveBeenCalledWith('indicator-1');

    await wrapper.find('.remove-indicator').trigger('click');
    expect(manager.removeIndicatorSeriesAndData).toHaveBeenCalledWith('indicator-1');
    expect(manager.updateMissingPaneHtmlElements).toHaveBeenCalled();
    expect(wrapper.emitted('remove-indicator')).toEqual([['indicator-1']]);

    wrapper.unmount();
    document.body.removeChild(pane);
  });

  it('debounces parameter changes and requests indicator data with market context', async () => {
    vi.useFakeTimers();
    const currentMarketStore = useCurrentMarketStore();
    const currentTimeframeStore = useCurrentTimeframeStore();
    const indicatorsStore = useIndicatorsStore();
    currentMarketStore.setMarket({
      symbol_id: 1,
      symbol: 'EURUSD',
      exchange: 'FX',
      market_type: 'forex',
      min_move: 0.0001,
      timezone: 'UTC',
    });
    currentTimeframeStore.setCurrentTimeframe({ label: 'M5', value: 'M5' });
    const updateParameters = vi
      .spyOn(indicatorsStore, 'updateIndicatorParameters')
      .mockReturnValue(createIndicator().parameters);
    const requestIndicator = vi
      .spyOn(indicatorsStore, 'requestIndicator')
      .mockResolvedValue('indicator-1');

    const wrapper = mount(IndicatorSettingsParameters, {
      props: {
        indicator: createIndicator(),
      },
      global: {
        stubs: {
          NScrollbar: SlotStub,
          NInput: NInputStub,
          NInputNumber: NInputNumberStub,
          NSelect: true,
          'n-scrollbar': SlotStub,
          'n-input': NInputStub,
          'n-input-number': NInputNumberStub,
          'n-select': true,
        },
      },
    });

    await wrapper.find('.n-input-number input').setValue('20');
    vi.advanceTimersByTime(199);
    expect(requestIndicator).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    await flushPromises();

    expect(updateParameters).toHaveBeenCalledWith('indicator-1', {
      length: 20,
      source: 'close',
    });
    expect(requestIndicator).toHaveBeenCalledWith('indicator-1', 7, {
      symbol: 'EURUSD',
      timeframe: 'M5',
      limit: 500,
      exchange: 'FX',
    }, {
      parameters: {
        length: 20,
        source: 'close',
      },
    });
  });

  it('emits style updates with the changed output styles', async () => {
    const wrapper = mount(IndicatorSettingsStyles, {
      props: {
        indicatorInfo,
      },
      global: {
        stubs: {
          NScrollbar: SlotStub,
          NH3: SlotStub,
          NColorPicker: NColorPickerStub,
          NInput: NInputStub,
          NInputNumber: NInputNumberStub,
          'n-scrollbar': SlotStub,
          'n-h3': SlotStub,
          'n-color-picker': NColorPickerStub,
          'n-input': NInputStub,
          'n-input-number': NInputNumberStub,
        },
      },
    });

    await wrapper.findAll('.n-input-number input')[0].setValue('4');

    expect(wrapper.emitted('update-styles')).toEqual([
      [{
        outputKey: 'sma',
        styles: {
          color: '#3366ff',
          lineWidth: 4,
          priceFormat: {
            precision: 2,
            minMove: 0.01,
          },
        } satisfies JsonObject,
      }],
    ]);
  });
});
