import { describe, expect, it } from 'vitest';
import {
  metricBounds,
  metricValue,
  metricScore,
  formatMetric,
} from '@/views/workspace/heatmap/heatmapMetrics';
import { savedHeatmap } from './heatmapFixtures';
describe('saved metric scales', () => {
  it('uses all saved successful members, preserving negative returns, zero and outliers', () => {
    const { runs } = savedHeatmap();
    expect(metricBounds(runs, 'return')).toEqual([-10.12345, 1000]);
    expect(metricBounds(runs, 'factor')).toEqual([0, 0]);
    expect(metricValue(runs[0], 'factor')).toBe(Infinity);
    expect(metricScore(Infinity, [0, 0], 'factor')).toBe(1);
    expect(metricScore(0, [0, 0], 'factor')).toBe(0.5);
    expect(metricBounds(runs, 'equity')).toEqual([10000, 10002]);
    expect(metricBounds(runs, 'drawdown')).toEqual([0, 2]);
    expect(metricScore(0, [0, 2], 'drawdown')).toBe(1);
    expect(metricScore(2, [0, 2], 'drawdown')).toBe(0);
    runs[2].status = 'failed';
    expect(metricBounds(runs, 'return')).toEqual([-10.12345, 0]);
  });
  it('never invents finite bounds for infinity-only or null-only results', () => {
    const { runs } = savedHeatmap();
    expect(metricBounds([runs[0]], 'factor')).toBeNull();
    expect(metricBounds([runs[2]], 'factor')).toBeNull();
    expect(metricValue(runs[2], 'factor')).toBeNull();
    expect(metricScore(-10, [-10, -10], 'return')).toBe(0.5);
    expect(formatMetric(-10.12345, 'return', true)).toBe('-10.12%');
    expect(formatMetric(-10.12345, 'return')).toBe('-10.12345%');
  });
});
