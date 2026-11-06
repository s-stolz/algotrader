import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { ChartManager } from '@/utils/chart/ChartManager';
import { IndicatorManager } from '@/utils/chart/IndicatorManager';
import { createTestChart } from './realChart.fixtures';

beforeEach(() => setActivePinia(createPinia()));
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function setup(negativeColor: string | undefined = '#f23645') {
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
      inputs: [],
      parameters: {},
      outputs: {
        macd: { type: 'line', plotOptions: { color: '#2962ff' } },
        signal: { type: 'line', plotOptions: { color: '#f23645' } },
        hist: {
          type: 'histogram',
          plotOptions: {
            color: '#089981',
            ...(negativeColor ? { negativeColor } : {}),
          },
        },
      },
    },
    [
      { timestamp_ms: 1000, hist: -2, macd: -3, signal: -1 },
      { timestamp_ms: 2000, hist: 0, macd: 0, signal: 0 },
      { timestamp_ms: 3000, hist: 2, macd: 3, signal: 1 },
    ],
    4,
  );
  const indicator = manager.indicatorsStore.getById(id)!;
  // Saved single-color styles predate the negative-color catalog default.
  indicator.styles.hist = { color: '#00aa00' };
  await manager.addIndicatorSeries(id);
  const plot = chart.series.get(`${id}_hist`)!.series;
  return { ...real, chart, manager, id, indicator, plot };
}

describe('MACD histogram rendering', () => {
  it('renders colored history behind the MACD and signal lines', async () => {
    const test = await setup();
    try {
      expect(test.plot.data()).toEqual([
        { time: 1, value: -2, color: '#f23645' },
        { time: 2, value: 0, color: '#00aa00' },
        { time: 3, value: 2, color: '#00aa00' },
      ]);
      expect(test.plot.options()).not.toHaveProperty('negativeColor');
      expect(test.plot.seriesOrder()).toBe(0);
      for (const output of ['macd', 'signal']) {
        expect(
          test.chart.series.get(`${test.id}_${output}`)!.series.seriesOrder(),
        ).toBeGreaterThan(0);
      }
      expect(test.chart.series.get(`${test.id}_signal`)!.series.data()).toEqual(
        [
          { time: 1, value: -1 },
          { time: 2, value: 0 },
          { time: 3, value: 1 },
        ],
      );
      test.indicator.data = [{ timestamp_ms: 1000, hist: -3 }];
      test.manager.refreshIndicatorSeries(test.id);
      expect(test.plot.data()).toEqual([
        { time: 1, value: -3, color: '#f23645' },
      ]);
    } finally {
      test.cleanup();
    }
  });

  it('recolors forming bars as live values cross zero', async () => {
    const test = await setup();
    try {
      for (const [value, color] of [
        [-1, '#f23645'],
        [0, '#00aa00'],
        [1, '#00aa00'],
      ] as const) {
        test.manager.updateIndicatorSeriesPoint(test.id, {
          timestamp_ms: 4000,
          hist: value,
        });
        expect(test.plot.data().at(-1)).toEqual({ time: 4, value, color });
      }
    } finally {
      test.cleanup();
    }
  });

  it('recolors existing bars and preserves the displayed live tail on palette edits', async () => {
    const test = await setup();
    try {
      test.manager.updateIndicatorSeriesPoint(test.id, {
        timestamp_ms: 4000,
        hist: -4,
      });
      expect(
        test.manager.updateIndicatorStyles(test.id, 'hist', {
          color: '#11ff11',
          negativeColor: '#ff1111',
        }),
      ).toBe(true);
      expect(test.plot.data()).toEqual([
        { time: 1, value: -2, color: '#ff1111' },
        { time: 2, value: 0, color: '#11ff11' },
        { time: 3, value: 2, color: '#11ff11' },
        { time: 4, value: -4, color: '#ff1111' },
      ]);
      test.manager.updateIndicatorSeriesPoint(test.id, {
        timestamp_ms: 5000,
        hist: -5,
      });
      expect(test.plot.data().at(-1)).toEqual({
        time: 5,
        value: -5,
        color: '#ff1111',
      });
    } finally {
      test.cleanup();
    }
  });

  it('keeps histograms without a sign palette single-colored', async () => {
    const test = await setup('');
    try {
      expect(test.plot.options()).toMatchObject({ color: '#00aa00' });
      expect(test.plot.data()).toEqual([
        { time: 1, value: -2 },
        { time: 2, value: 0 },
        { time: 3, value: 2 },
      ]);
    } finally {
      test.cleanup();
    }
  });
});
