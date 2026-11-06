import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';
import type { MouseEventParams, Time, UTCTimestamp } from 'lightweight-charts';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { ChartManager } from '@/utils/chart/ChartManager';
import {
  getReadoutOutputs,
  readIndicatorValues,
} from '@/components/Chart/Indicator/indicatorReadout';
import IndicatorValues from '@/components/Chart/Indicator/IndicatorValues.vue';
import { createTestChart } from '../../../utils/chart/realChart.fixtures';
import type { IndicatorInfo } from '@/types/contracts';

const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'macd',
  name: 'MACD',
  overlay: false,
  inputs: [],
  parameters: {},
  outputs: {
    timestamp: { type: 'time' },
    macd: { type: 'line', plotOptions: { color: '#ff0000' } },
    signal: { type: 'line', label: 'Signal' },
    hist: { type: 'histogram' },
  },
};

function createIndicator(metadata = info) {
  const store = useIndicatorsStore();
  const id = store.addIndicator(metadata, [], metadata.id);
  return store.getById(id)!;
}

beforeEach(() => setActivePinia(createPinia()));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('indicator readouts', () => {
  it('uses the plotted series formatter, including zero and histogram values', () => {
    const real = createTestChart();
    const manager = new ChartManager();
    manager.chart = real.chart;
    const indicator = createIndicator();
    const event: MouseEventParams<Time> = {
      time: 60 as UTCTimestamp,
      seriesData: new Map(),
    };
    try {
      for (const [key, value] of Object.entries({
        macd: 0,
        signal: 1.23456,
        hist: -2.1,
      })) {
        const series = manager.addSeries(
          `${indicator._id}_${key}`,
          key === 'hist' ? 'histogram' : 'line',
          [{ time: 60, value }],
          { priceFormat: { type: 'price', minMove: 0.00001, precision: 5 } },
        )!;
        event.seriesData.set(series, { time: event.time!, value });
      }
      expect(readIndicatorValues(indicator, event, manager.series)).toEqual({
        macd: '0.00000',
        signal: '1.23456',
        hist: '−2.10000',
      });
      const macd = manager.series.get(`${indicator._id}_macd`)!.series;
      event.seriesData.set(macd, { time: 120 as UTCTimestamp, value: 42 });
      const signal = manager.series.get(`${indicator._id}_signal`)!.series;
      event.seriesData.set(signal, { time: event.time!, value: NaN });
      event.seriesData.delete(
        manager.series.get(`${indicator._id}_hist`)!.series,
      );
      expect(readIndicatorValues(indicator, event, manager.series)).toEqual({
        macd: '—',
        signal: '—',
        hist: '—',
      });
    } finally {
      real.cleanup();
    }
  });

  it('reads Opening Range as known at that candle and omits internal fields', () => {
    const real = createTestChart();
    const manager = new ChartManager();
    manager.chart = real.chart;
    const indicator = createIndicator({
      ...info,
      indicator_id: 'opening_range',
      outputs: {
        range_high: {
          type: 'opening_range',
          label: 'Range',
          plotOptions: { color: '#123456' },
        },
      },
    });
    indicator.data = [
      { timestamp_ms: 60_000, range_high: 12.5, range_low: 10, ready: 0 },
      { timestamp_ms: 120_000, range_high: 20, range_low: 8, ready: 1 },
    ];
    try {
      manager.addSeries('ohlc', 'candlestick', [], {
        priceFormat: { type: 'price', minMove: 0.001, precision: 3 },
      });
      const event: MouseEventParams<Time> = {
        time: 60 as UTCTimestamp,
        seriesData: new Map(),
      };
      expect(readIndicatorValues(indicator, event, manager.series)).toEqual({
        range_high: '12.500',
        range_low: '10.000',
      });
      expect(getReadoutOutputs(indicator)).toEqual([
        { key: 'range_high', label: 'High', color: '#123456' },
        { key: 'range_low', label: 'Low', color: '#123456' },
      ]);
      event.time = 90 as UTCTimestamp;
      expect(readIndicatorValues(indicator, event, manager.series)).toEqual({
        range_high: '—',
        range_low: '—',
      });
    } finally {
      real.cleanup();
    }
  });

  it('renders labels and user colors while retaining captured values', async () => {
    const indicator = createIndicator();
    indicator.styles.macd = { color: '#abcdef' };
    const wrapper = mount(IndicatorValues, { props: { indicator } });
    expect(wrapper.text()).toContain('macd:  —');
    expect(wrapper.findAll('.indicator-value')).toHaveLength(3);
    expect(wrapper.get('.indicator-value').attributes('style')).toContain(
      'rgb(171, 205, 239)',
    );
    await wrapper.setProps({
      readout: { macd: '1.23', signal: '0.00', hist: '-0.10' },
    });
    expect(wrapper.text()).toContain('Signal:  0.00');
    indicator.lastLivePoint = { timestamp_ms: 60_000, macd: 99 };
    await wrapper.setProps({ indicator: { ...indicator } });
    expect(wrapper.text()).toContain('1.23');
    expect(wrapper.text()).not.toContain('99');
    await wrapper.setProps({
      indicator: {
        ...indicator,
        info: { ...info, outputs: { macd: info.outputs.macd } },
      },
    });
    expect(wrapper.text()).toBe('1.23');
    wrapper.unmount();
  });
});
