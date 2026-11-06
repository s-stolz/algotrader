import type { MouseEventParams, Time } from 'lightweight-charts';
import type { StoreIndicator } from '@/stores/indicatorsStore';
import type { ChartSeriesInfo } from '@/utils/chart/ChartManager';
import { isChartSeriesType } from '@/utils/chart/seriesTypes';
import { buildRangeBoxes, rangeStyle } from '@/utils/chart/openingRange/model';

export type IndicatorReadout = Record<string, string>;

export function getReadoutOutputs(indicator: StoreIndicator) {
  if (indicator.info.indicator_id === 'opening_range') {
    const color = rangeStyle(
      indicator.styles.range_high ??
        indicator.info.outputs.range_high?.plotOptions,
    ).color;
    return [
      { key: 'range_high', label: 'High', color },
      { key: 'range_low', label: 'Low', color },
    ];
  }
  return Object.entries(indicator.info.outputs)
    .filter(([, output]) => isChartSeriesType(output.type))
    .map(([key, output]) => {
      const options = indicator.styles[key] ?? output.plotOptions;
      const color = options?.color ?? options?.lineColor;
      return {
        key,
        label: typeof output.label === 'string' ? output.label : key,
        color: typeof color === 'string' ? color : undefined,
      };
    });
}

function findRangePoint(indicator: StoreIndicator, time: Time | undefined) {
  if (typeof time !== 'number') return undefined;
  const matches = (timestamp: number) => Math.floor(timestamp / 1000) === time;
  if (
    indicator.lastLivePoint &&
    matches(indicator.lastLivePoint.timestamp_ms)
  ) {
    return indicator.lastLivePoint;
  }
  const data = indicator.data;
  let left = 0;
  let right = data.length - 1;
  while (left <= right) {
    const middle = Math.floor((left + right) / 2);
    const point = data[middle];
    if (matches(point.timestamp_ms)) return point;
    if (point.timestamp_ms / 1000 < time) left = middle + 1;
    else right = middle - 1;
  }
  return undefined;
}

export function readIndicatorValues(
  indicator: StoreIndicator,
  event: MouseEventParams<Time>,
  series: ReadonlyMap<string, ChartSeriesInfo>,
): IndicatorReadout {
  const isRange = indicator.info.indicator_id === 'opening_range';
  const rangePoint = isRange
    ? findRangePoint(indicator, event.time)
    : undefined;
  const range = rangePoint ? buildRangeBoxes([rangePoint])[0] : undefined;
  return Object.fromEntries(
    getReadoutOutputs(indicator).map(({ key }) => {
      const plot = series.get(isRange ? 'ohlc' : `${indicator._id}_${key}`);
      const point = plot ? event.seriesData.get(plot.series) : undefined;
      const value = isRange
        ? range?.[key === 'range_high' ? 'high' : 'low']
        : point && point.time === event.time && 'value' in point
          ? point.value
          : undefined;
      return [
        key,
        typeof value === 'number' && Number.isFinite(value) && plot
          ? plot.series.priceFormatter().format(value)
          : '—',
      ];
    }),
  );
}
