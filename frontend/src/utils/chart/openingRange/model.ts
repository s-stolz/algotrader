import type { IndicatorDataPoint, JsonObject } from '@/types/contracts';

export interface RangeBox {
  start: number;
  end: number;
  extensionEnd: number;
  high: number;
  low: number;
  ready: boolean;
}

export interface RangeStyle {
  color: string;
  fillColor: string;
  lineWidth: number;
  showExtensions: boolean;
}

export function rangeStyle(options: JsonObject = {}): RangeStyle {
  return {
    color: typeof options.color === 'string' ? options.color : '#2962ff',
    fillColor:
      typeof options.fillColor === 'string'
        ? options.fillColor
        : 'rgba(41, 98, 255, 0.12)',
    lineWidth:
      typeof options.lineWidth === 'number'
        ? Math.max(1, options.lineWidth)
        : 1,
    showExtensions: options.showExtensions !== false,
  };
}

export function buildRangeBoxes(
  data: readonly IndicatorDataPoint[],
): RangeBox[] {
  const sessions = new Map<number, { timestamp: number; box: RangeBox }>();
  for (const point of data) {
    const {
      timestamp_ms: timestamp,
      range_start_ms: start,
      range_end_ms: end,
      extension_end_ms: extensionEnd,
      range_high: high,
      range_low: low,
    } = point;
    if (
      typeof start !== 'number' ||
      typeof end !== 'number' ||
      typeof extensionEnd !== 'number' ||
      typeof high !== 'number' ||
      typeof low !== 'number'
    )
      continue;
    if (
      ![timestamp, start, end, extensionEnd, high, low].every(
        Number.isFinite,
      ) ||
      timestamp < start ||
      end <= start ||
      extensionEnd < end ||
      high < low
    )
      continue;
    if ((sessions.get(start)?.timestamp ?? -Infinity) > timestamp) continue;
    sessions.set(start, {
      timestamp,
      box: {
        start: start / 1000,
        end: Math.min(timestamp, end) / 1000,
        extensionEnd: extensionEnd / 1000,
        high,
        low,
        ready: point.ready === 1,
      },
    });
  }
  return [...sessions.values()]
    .map(({ box }) => box)
    .sort((a, b) => a.start - b.start);
}
