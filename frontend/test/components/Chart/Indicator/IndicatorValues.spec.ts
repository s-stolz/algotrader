import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';
import type { UTCTimestamp } from 'lightweight-charts';
import IndicatorValues from '@/components/Chart/Indicator/IndicatorValues.vue';
import { readIndicatorValues } from '@/components/Chart/Indicator/indicatorReadout';
import { ChartManager } from '@/utils/chart/ChartManager';
import { IndicatorManager } from '@/utils/chart/IndicatorManager';
import { createTestChart } from '../../../utils/chart/realChart.fixtures';

beforeEach(() => setActivePinia(createPinia()));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('matches hovered bar colors, including negatives rounded to zero', async () => {
  const real = createTestChart();
  const chart = new ChartManager();
  chart.chart = real.chart;
  vi.spyOn(chart, 'getPaneHtmlElement').mockResolvedValue(null);
  const manager = new IndicatorManager(chart);
  const id = manager.indicatorsStore.addIndicator(
    {
      id: 4,
      indicator_id: 'macd',
      name: 'MACD',
      overlay: false,
      parameters: {},
      inputs: [],
      outputs: {
        hist: {
          type: 'histogram',
          plotOptions: {
            color: '#089981',
            negativeColor: '#f23645',
            priceFormat: { minMove: 0.01, precision: 2 },
          },
        },
      },
    },
    [
      { timestamp_ms: 1000, hist: -0.000001 },
      { timestamp_ms: 2000, hist: 0 },
      { timestamp_ms: 3000, hist: 1 },
    ],
    4,
  );
  const indicator = manager.indicatorsStore.getById(id)!;
  const wrapper = mount(IndicatorValues, { props: { indicator } });
  try {
    await manager.addIndicatorSeries(id);
    const series = chart.series.get(`${id}_hist`)!.series;
    const hover = async (index: number) => {
      const point = series.dataByIndex(index)!;
      await wrapper.setProps({
        readout: readIndicatorValues(
          indicator,
          {
            time: point.time,
            seriesData: new Map([[series, point]]),
          },
          chart.series,
        ),
      });
    };
    await hover(0);
    expect(wrapper.text()).toBe('−0.00');
    expect(wrapper.get('.indicator-value').attributes('style')).toContain(
      'rgb(242, 54, 69)',
    );
    for (const index of [1, 2]) {
      await hover(index);
      expect(wrapper.get('.indicator-value').attributes('style')).toContain(
        'rgb(8, 153, 129)',
      );
    }
    manager.updateIndicatorStyles(id, 'hist', {
      color: '#00ff00',
      negativeColor: '#ff0000',
    });
    await hover(0);
    expect(wrapper.get('.indicator-value').attributes('style')).toContain(
      'rgb(255, 0, 0)',
    );
    await hover(1);
    expect(wrapper.get('.indicator-value').attributes('style')).toContain(
      'rgb(0, 255, 0)',
    );
    await wrapper.setProps({
      readout: readIndicatorValues(
        indicator,
        {
          time: 4 as UTCTimestamp,
          seriesData: new Map(),
        },
        chart.series,
      ),
    });
    expect(wrapper.text()).toBe('—');
  } finally {
    wrapper.unmount();
    real.cleanup();
  }
});
