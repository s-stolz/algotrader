import type { ChartSeriesType } from './ChartManager';

const CHART_SERIES_TYPES = new Set<ChartSeriesType>([
  'line',
  'area',
  'bar',
  'baseline',
  'candlestick',
  'histogram',
]);

export function isChartSeriesType(
  value: string | undefined,
): value is ChartSeriesType {
  return (
    value !== undefined && CHART_SERIES_TYPES.has(value as ChartSeriesType)
  );
}
