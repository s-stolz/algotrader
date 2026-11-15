import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ChartManager } from '@/utils/chart/ChartManager';
import { IndicatorManager } from '@/utils/chart/IndicatorManager';
import type { IndicatorDataPoint, IndicatorInfo } from '@/types/contracts';
import { createTestChart } from './realChart.fixtures';

vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn().mockResolvedValue(undefined) },
}));

const info: IndicatorInfo = {
  id: 1,
  indicator_id: 'currency_strength',
  name: 'Currency Strength',
  overlay: false,
  inputs: [],
  outputs: {
    timestamp: { type: 'time' },
    EUR: { type: 'line', plotOptions: {} },
    USD: { type: 'line', plotOptions: {} },
  },
  parameters: {},
};

beforeEach(() => setActivePinia(createPinia()));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it.each<IndicatorDataPoint[][]>([
  [[]],
  [[{ timestamp_ms: 1000, EUR: null, USD: null }]],
])(
  'keeps an empty indicator pane available through data changes and removal',
  async (data) => {
    const surface = createTestChart();
    try {
      const chart = new ChartManager();
      chart.chart = surface.chart;
      chart.addSeries('ohlc', 'candlestick', [
        { time: 1, open: 100, high: 110, low: 90, close: 105 },
      ]);
      const manager = new IndicatorManager(chart);
      const store = manager.indicatorsStore;
      const id = store.addIndicator(info, data, 1);
      const adding = manager.addIndicatorSeries(id);
      surface.flush();
      await adding;

      expect(surface.chart.panes()).toHaveLength(2);
      expect(store.getById(id)?.paneHtmlElement).toBeInstanceOf(HTMLElement);
      expect(chart.series.get(`${id}_EUR`)?.data).toEqual([]);

      store.updateIndicatorData(id, [{ timestamp_ms: 1000, EUR: 2, USD: -2 }]);
      manager.refreshIndicatorSeries(id);
      expect(chart.series.get(`${id}_EUR`)?.data).toEqual([
        { time: 1, value: 2 },
      ]);
      store.updateIndicatorData(id, []);
      manager.refreshIndicatorSeries(id);
      expect(surface.chart.panes()).toHaveLength(2);
      expect(chart.series.get(`${id}_EUR`)?.data).toEqual([]);

      manager.removeIndicatorSeriesAndData(id);
      expect(store.exists(id)).toBe(false);
      expect(surface.chart.panes()).toHaveLength(1);
    } finally {
      surface.cleanup();
    }
  },
);
