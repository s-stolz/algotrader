import {
  chartAreaMocks,
  candle,
  eurUsdM5Key,
  setupStores,
  mountChartArea,
  latestChartSessionAdapter,
  setupChartAreaTests,
} from './ChartArea.fixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

describe('ChartArea legend', () => {
  setupChartAreaTests();

  it('updates the OHLC legend from the chart crosshair callback', async () => {
    setupStores();
    const wrapper = mountChartArea();
    await flushPromises();
    await latestChartSessionAdapter().renderCandles(eurUsdM5Key, [
      candle(300_000),
    ]);

    chartAreaMocks.crosshairHandler?.({
      time: 300,
      point: { x: 1, y: 1 },
      seriesData: new Map([
        [
          chartAreaMocks.ohlcSeries,
          {
            open: 1.1,
            high: 1.3,
            low: 1,
            close: 1.2,
          },
        ],
      ]),
    });

    expect(wrapper.find('.legend').text()).toContain('O: 1.1');
    expect(wrapper.find('.legend').text()).toContain('H: 1.3');
    expect(wrapper.find('.legend').text()).toContain('L: 1');
    expect(wrapper.find('.legend').text()).toContain('C: 1.2');
  });
});
