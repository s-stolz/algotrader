import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { nextTick, watch } from 'vue';
import type { MouseEventParams, Time, UTCTimestamp } from 'lightweight-charts';
import { createChartSessionAdapter } from '@/components/Chart/chartSessionAdapter';
import { readIndicatorValues } from '@/components/Chart/Indicator/indicatorReadout';
import { useIndicatorsStore } from '@/stores/indicatorsStore';
import { useCandlesticksStore } from '@/stores/candlesticksStore';
import { ChartManager } from '@/utils/chart/ChartManager';
import { IndicatorManager } from '@/utils/chart/IndicatorManager';
import { createTestChart } from '../../utils/chart/realChart.fixtures';

vi.mock('@/utils/websocketService', () => ({
  wsService: { send: vi.fn().mockResolvedValue(undefined) },
}));
beforeEach(() => setActivePinia(createPinia()));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('clears old indicator history and series while the next session loads', async () => {
  const surface = createTestChart();
  const chart = new ChartManager();
  chart.chart = surface.chart;
  vi.spyOn(chart, 'getPaneHtmlElement').mockResolvedValue(null);
  const manager = new IndicatorManager(chart);
  const indicatorsStore = useIndicatorsStore();
  const id = indicatorsStore.addIndicator(
    {
      id: 1,
      indicator_id: 'sma',
      name: 'SMA',
      overlay: true,
      inputs: [],
      parameters: {},
      outputs: { sma: { type: 'line' } },
    },
    [{ timestamp_ms: 300_000, sma: 1.25 }],
    1,
  );
  const indicator = indicatorsStore.getById(id)!;
  const adapter = createChartSessionAdapter({
    indicatorsStore,
    candlesticksStore: useCandlesticksStore(),
    currentChartSessionKey: () => ({
      symbol: 'GBPUSD',
      exchange: 'FX',
      timeframe: 'M5',
    }),
    renderCandlesticks: vi.fn(),
    shouldScrollToRealTime: () => false,
  });
  const stop = watch(
    () => indicator.dataVersion,
    () => manager.refreshIndicatorSeries(id),
  );
  try {
    await manager.addIndicatorSeries(id);
    const plot = chart.series.get(`${id}_sma`)!.series;
    const capture = () => {
      const point = plot.dataByIndex(0);
      const event: MouseEventParams<Time> = {
        time: 300 as UTCTimestamp,
        seriesData: point ? new Map([[plot, point]]) : new Map(),
      };
      return readIndicatorValues(indicator, event, chart.series);
    };
    expect(capture()).toEqual({ sma: '1.25' });
    adapter.resetIndicatorHistory?.();
    await nextTick();
    expect(capture()).toEqual({ sma: '—' });
    expect(indicator.data).toEqual([]);
    expect(indicator.lastLivePoint).toBeNull();
    expect(indicatorsStore.exists(id)).toBe(true);
    indicatorsStore.updateIndicatorData(id, [
      { timestamp_ms: 300_000, sma: 2.5 },
    ]);
    await nextTick();
    expect(capture()).toEqual({ sma: '2.50' });
  } finally {
    stop();
    surface.cleanup();
  }
});
