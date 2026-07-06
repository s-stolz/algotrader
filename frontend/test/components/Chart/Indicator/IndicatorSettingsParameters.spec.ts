import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import IndicatorSettingsParameters from '@/components/Chart/Indicator/IndicatorSettingsParameters.vue';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { useIndicatorsStore, type StoreIndicator } from '@/stores/indicatorsStore';
import type { IndicatorInfo } from '@/types/contracts';

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

describe('IndicatorSettingsParameters', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
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
});
