import type { EChartsOption } from 'echarts';
import { designTokens } from '@/design/tokens';
import type { HeatmapDimension } from '@/types/backtest/heatmapSnapshot';
import type { HeatmapCell } from './heatmapGrid';
import { metricScore, type HeatmapMetric } from './heatmapMetrics';
const { chart, color, font } = designTokens;
export const palette = [
  chart.heatmapWorst,
  chart.heatmapMidpoint,
  chart.heatmapBest,
];
export const specialStates = {
  excluded: { color: chart.heatmapExcluded, symbol: '×', label: 'No Run' },
  unavailable: {
    color: chart.heatmapUnavailable,
    symbol: '◇',
    label: 'Unavailable result',
  },
  error: { color: chart.heatmapReadError, symbol: '!', label: 'Read failed' },
};
export function heatmapChart(
  cells: HeatmapCell[],
  x: HeatmapDimension,
  y: HeatmapDimension,
  metric: HeatmapMetric,
  bounds: [number, number] | null,
  pending: boolean,
  selectedIds: string[],
): EChartsOption {
  const selected = new Set(selectedIds);
  const item = (cell: HeatmapCell, score: number) => ({
    value: [cell.x, cell.y, score],
    cell,
    itemStyle: {
      borderWidth: cell.run && selected.has(cell.run.run_id) ? 3 : 1,
      borderColor:
        cell.run && selected.has(cell.run.run_id)
          ? chart.heatmapSelection
          : designTokens.color.panel,
    },
    label: {
      show: cell.value === Infinity,
      formatter: '∞',
      color: color.onInteractive,
      fontFamily: font.ui,
    },
  });
  const axis = (field: HeatmapDimension) => ({
    type: 'category' as const,
    data: field.options.map((option) => option.label),
    name: field.label,
    axisLabel: { color: designTokens.color.body, fontFamily: font.ui },
    nameTextStyle: { color: designTokens.color.muted, fontFamily: font.ui },
    splitArea: { show: false },
  });
  return {
    animation: false,
    textStyle: { fontFamily: font.ui },
    aria: {
      enabled: true,
      description:
        `${x.label} by ${y.label}. ` +
        'Use the Runs table for keyboard comparison and inspection.',
    },
    grid: { left: 90, right: 24, top: 35, bottom: 65 },
    xAxis: { ...axis(x), nameLocation: 'middle', nameGap: 38 },
    yAxis: axis(y),
    tooltip: {
      trigger: 'item',
      textStyle: { fontFamily: font.ui },
      renderMode: 'richText',
      confine: true,
      formatter: (params: unknown) =>
        (params as { data: { cell: HeatmapCell } }).data.cell.description,
    },
    visualMap: [
      {
        show: false,
        min: 0,
        max: 1,
        dimension: 2,
        seriesIndex: 0,
        inRange: { color: palette },
      },
      {
        type: 'piecewise',
        show: false,
        dimension: 2,
        seriesIndex: 1,
        pieces: [
          { value: 0, color: specialStates.excluded.color },
          { value: 1, color: specialStates.unavailable.color },
          { value: 2, color: chart.heatmapAwaiting },
        ],
      },
    ],
    series: [
      {
        type: 'heatmap',
        data: cells
          .filter((cell) => cell.state === 'ready' && !pending)
          .map((cell) => item(cell, metricScore(cell.value!, bounds, metric))),
      },
      {
        type: 'heatmap',
        data: cells
          .filter((cell) => cell.state !== 'ready' || pending)
          .map((cell) => ({
            ...item(
              cell,
              cell.state === 'excluded'
                ? 0
                : cell.state === 'unavailable'
                  ? 1
                  : 2,
            ),
            label: {
              show: true,
              formatter:
                cell.state === 'ready'
                  ? cell.value === Infinity
                    ? '∞'
                    : ''
                  : specialStates[cell.state].symbol,
              color: chart.heatmapSymbol,
              fontSize: 15,
              fontFamily: font.ui,
            },
          })),
      },
    ],
  };
}
