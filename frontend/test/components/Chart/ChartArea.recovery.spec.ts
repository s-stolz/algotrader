import { expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import {
  setupChartAreaTests,
  setupStores,
  mountChartArea,
  chartAreaMocks,
  latestChartSessionAdapter,
  candle,
} from './ChartArea.fixtures';

setupChartAreaTests();
it('preserves the visible time range when recovery inserts missing candles', async () => {
  setupStores();
  const wrapper = mountChartArea();
  await flushPromises();
  const visibleRange = { from: 300, to: 1200 };
  const timeScale = {
    getVisibleRange: vi.fn(() => visibleRange),
    getVisibleLogicalRange: vi.fn(() => ({ from: 0.25, to: 10.75 })),
    timeToIndex: vi.fn(() => 5),
    setVisibleLogicalRange: vi.fn(),
  };
  Object.assign(chartAreaMocks.infrastructure.chartManager, {
    chart: { timeScale: () => timeScale },
  });
  chartAreaMocks.infrastructure.scrollToRealTime.mockClear();
  try {
    latestChartSessionAdapter().recovery.merge([candle(600_000)], []);
    expect(timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({
      from: 0.25,
      to: 10.75,
    });
    expect(
      chartAreaMocks.infrastructure.scrollToRealTime,
    ).not.toHaveBeenCalled();
  } finally {
    Reflect.deleteProperty(chartAreaMocks.infrastructure.chartManager, 'chart');
    wrapper.unmount();
  }
});
