import { expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { CandlestickSeries, type UTCTimestamp } from 'lightweight-charts';
import { createTestChart } from '../../utils/chart/realChart.fixtures';
import {
  setupChartAreaTests,
  setupStores,
  mountChartArea,
  chartAreaMocks,
  latestChartSessionAdapter,
  candle,
} from './ChartArea.fixtures';

setupChartAreaTests();
it.each([false, true])(
  'keeps zoom and whitespace when filling a gap: %s',
  async (fillGap) => {
    const { candlesticksStore } = setupStores();
    const wrapper = mountChartArea();
    await flushPromises();
    const real = createTestChart();
    const series = real.chart.addSeries(CandlestickSeries);
    const history = Array.from({ length: 100 }, (_, i) =>
      candle((i + 1) * 120_000),
    );
    const apply = () =>
      series.setData(
        candlesticksStore.data.map((c) => ({
          ...c,
          time: c.time as UTCTimestamp,
        })),
      );
    candlesticksStore.replace(history);
    apply();
    Object.assign(chartAreaMocks.infrastructure.chartManager, {
      chart: real.chart,
    });
    chartAreaMocks.infrastructure.addCandlestickData.mockImplementation(() => {
      apply();
      return chartAreaMocks.ohlcSeries;
    });
    const range = { from: 40.25, to: 104.75 };
    real.chart.timeScale().setVisibleLogicalRange(range);
    real.flush();
    expect(real.chart.timeScale().getVisibleLogicalRange()).toEqual(range);
    try {
      latestChartSessionAdapter().recovery.merge(
        [candle(fillGap ? 11_940_000 : 12_000_000, 1.7)],
        [],
      );
      real.flush();
      expect(real.chart.timeScale().getVisibleLogicalRange()).toEqual(
        fillGap ? { from: range.from + 1, to: range.to + 1 } : range,
      );
    } finally {
      Reflect.deleteProperty(
        chartAreaMocks.infrastructure.chartManager,
        'chart',
      );
      real.cleanup();
      wrapper.unmount();
      vi.unstubAllGlobals();
    }
  },
);
