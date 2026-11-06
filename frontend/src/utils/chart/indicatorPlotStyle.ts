import type { StoreIndicator } from '@/stores/indicators/types';
import type { JsonObject } from '@/types/contracts';
import type { ChartValuePoint } from './ChartManager';

export function resolveIndicatorPlotStyle(
  indicator: Pick<StoreIndicator, 'info' | 'styles'>,
  outputKey: string,
): JsonObject {
  return {
    ...indicator.info.outputs[outputKey]?.plotOptions,
    ...indicator.styles[outputKey],
  };
}

export function colorIndicatorPoint(
  point: ChartValuePoint,
  outputType?: string,
  style?: JsonObject,
): ChartValuePoint {
  const result = { time: point.time, value: point.value };
  if (outputType !== 'histogram' || typeof style?.negativeColor !== 'string')
    return result;
  const color = point.value < 0 ? style.negativeColor : style.color;
  return typeof color === 'string' ? { ...result, color } : result;
}
