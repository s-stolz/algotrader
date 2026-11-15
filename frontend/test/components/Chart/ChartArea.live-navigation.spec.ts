import type { LogicalRange } from 'lightweight-charts';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import {
  setupChartAreaTests,
  setupStores,
  chartAreaMocks,
  mountChartArea,
} from './ChartArea.fixtures';
import { chartCandle } from './chartSession.fixtures';
setupChartAreaTests();
it.each([
  { historical: true, visible: false },
  { historical: false, visible: true },
  { historical: false, visible: false },
])(
  'returns to latest without refreshing a loaded live chart: %j',
  async ({ historical, visible }) => {
    const { createChartSession } = await vi.importActual<
      typeof import('@/components/Chart/chartSession')
    >('@/components/Chart/chartSession');
    const fetchLatest = vi.fn(async () => [chartCandle(300_000)]);
    chartAreaMocks.createChartSession.mockImplementation((adapter) => {
      (adapter as Parameters<typeof createChartSession>[0]).fetchCandles =
        fetchLatest;
      const session = createChartSession(
        adapter as Parameters<typeof createChartSession>[0],
      );
      return {
        setSession: vi.fn(session.setSession.bind(session)),
        stop: vi.fn(session.stop.bind(session)),
        requestOlderHistory: vi.fn(session.requestOlderHistory.bind(session)),
      };
    });
    const { candlesticksStore } = setupStores();
    const wrapper = mountChartArea();
    try {
      await flushPromises();
      useIndicatorsStore().historicalMode = historical;
      chartAreaMocks.visibleRangeHandler?.(
        (visible
          ? { from: -50, to: 10 }
          : { from: -100, to: -20 }) as LogicalRange,
      );
      const scrollToPosition = vi.fn();
      Object.assign(chartAreaMocks.infrastructure.chartManager, {
        chart: {
          timeScale: () => ({ scrollToPosition, applyOptions: vi.fn() }),
        },
      });
      fetchLatest.mockClear();
      await wrapper.get('[aria-label="Go to latest candle"]').trigger('click');
      await flushPromises();
      expect(fetchLatest).toHaveBeenCalledTimes(historical ? 1 : 0);
      if (!historical)
        expect(scrollToPosition).toHaveBeenCalledTimes(visible ? 0 : 1);
      expect(candlesticksStore.data).toEqual([chartCandle(300_000)]);
    } finally {
      Reflect.deleteProperty(
        chartAreaMocks.infrastructure.chartManager,
        'chart',
      );
      wrapper.unmount();
    }
  },
);
