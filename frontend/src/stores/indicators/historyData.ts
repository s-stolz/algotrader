import type {
  IndicatorDataPoint,
  IndicatorUpdateMessage,
} from '@/types/contracts';
import type { IndicatorLoadedCandleRange } from './types';

export function trimDataToRange(
  data: readonly IndicatorDataPoint[],
  range: IndicatorLoadedCandleRange | null,
): IndicatorDataPoint[] {
  if (!range) return [...data];

  return data.filter((point) => {
    const timestampMs = Number(point.timestamp_ms);
    return (
      Number.isFinite(timestampMs) &&
      timestampMs >= range.oldestTimestampMs &&
      timestampMs <= range.newestTimestampMs
    );
  });
}

export function mergeIndicatorData(
  existingData: readonly IndicatorDataPoint[],
  incomingData: readonly IndicatorDataPoint[],
  range: IndicatorLoadedCandleRange | null,
): IndicatorDataPoint[] {
  const byTimestamp = new Map<number, IndicatorDataPoint>();

  for (const point of incomingData) {
    const timestampMs = Number(point.timestamp_ms);
    if (Number.isFinite(timestampMs)) {
      byTimestamp.set(timestampMs, { ...point, timestamp_ms: timestampMs });
    }
  }

  for (const point of existingData) {
    const timestampMs = Number(point.timestamp_ms);
    if (Number.isFinite(timestampMs)) {
      byTimestamp.set(timestampMs, { ...point, timestamp_ms: timestampMs });
    }
  }

  return trimDataToRange(
    Array.from(byTimestamp.values()).sort(
      (left, right) => left.timestamp_ms - right.timestamp_ms,
    ),
    range,
  );
}

export function mergeLivePoint(
  lastLivePoint: IndicatorDataPoint | null,
  message: IndicatorUpdateMessage,
): IndicatorDataPoint | null {
  const timestampMs = Number(message.timestamp_ms);
  if (!Number.isFinite(timestampMs)) return null;

  const point: IndicatorDataPoint = {
    timestamp_ms: timestampMs,
    ...message.values,
  };

  if (!lastLivePoint) {
    return point;
  }

  if (Number(lastLivePoint.timestamp_ms) === timestampMs) {
    const merged: IndicatorDataPoint = { ...lastLivePoint, ...point };
    return merged;
  }

  if (Number(lastLivePoint.timestamp_ms) < timestampMs) {
    return point;
  }

  return null;
}
