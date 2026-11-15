import { afterEach, expect, it, vi } from 'vitest';
import { ChartManager } from '@/utils/chart/ChartManager';
import { createTestChart } from './realChart.fixtures';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('keeps a later manual pane separate when strategy panes restore afterward', () => {
  const surface = createTestChart();
  try {
    const chart = new ChartManager();
    chart.chart = surface.chart;
    chart.addSeries('ohlc', 'candlestick', []);
    const manual = chart.addSeries('manual_rsi', 'line', [], {}, 2);
    const strategy = chart.addSeries('strategy_rsi', 'line', [], {}, 1);
    expect(surface.chart.panes()).toHaveLength(3);
    expect(manual?.getPane().paneIndex()).toBe(2);
    expect(strategy?.getPane().paneIndex()).toBe(1);
    chart.removeSeries('strategy_rsi');
    expect(surface.chart.panes()).toHaveLength(2);
    expect(manual?.getPane().paneIndex()).toBe(1);
    chart.removeSeries('manual_rsi');
    expect(surface.chart.panes()).toHaveLength(1);
  } finally {
    surface.cleanup();
  }
});
