import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import Indicator from '@/components/Chart/Indicator/Indicator.vue';
import type { StoreIndicator } from '@/stores/indicatorsStore';
import type { IndicatorInfo } from '@/types/contracts';

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

describe('Indicator', () => {
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
});
