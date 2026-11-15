import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { ChartManager } from '@/utils/chart/ChartManager';
import { IndicatorManager } from '@/utils/chart/IndicatorManager';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { createTestChart } from './realChart.fixtures';

beforeEach(() => setActivePinia(createPinia()));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it.each([true, false])(
  'uses market precision only for price overlays: %s',
  async (overlay) => {
    useCurrentMarketStore().setMarket({
      symbol: 'EURUSD',
      symbol_id: 1,
      exchange: 'FX',
      market_type: 'FOREX',
      min_move: 0.00001,
    });
    const real = createTestChart();
    const chart = new ChartManager();
    chart.chart = real.chart;
    vi.spyOn(chart, 'getPaneHtmlElement').mockResolvedValue(null);
    const manager = new IndicatorManager(chart);
    const id = manager.indicatorsStore.addIndicator(
      {
        id: 3,
        indicator_id: 'bbands',
        name: 'Bollinger Bands',
        overlay,
        inputs: [],
        parameters: {},
        outputs: { mid: { type: 'line', plotOptions: {} } },
      },
      [{ timestamp_ms: 60_000, mid: 1.11436 }],
      3,
    );
    try {
      await manager.addIndicatorSeries(id);
      expect(
        chart.series.get(`${id}_mid`)!.series.priceFormatter().format(1.11436),
      ).toBe(overlay ? '1.11436' : '1.11');
      useCurrentMarketStore().min_move = 0.001;
      manager.refreshIndicatorSeries(id);
      expect(
        chart.series.get(`${id}_mid`)!.series.priceFormatter().format(1.11436),
      ).toBe(overlay ? '1.114' : '1.11');
    } finally {
      real.cleanup();
    }
  },
);
