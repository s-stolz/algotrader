import { markRaw } from 'vue';
import type {
  IndicatorDataPoint,
  IndicatorUpdateMessage,
} from '@/types/contracts';
import type { IndicatorLoadedCandleRange, StoreIndicator } from './types';

export function replaceIndicatorData(
  indicator: Pick<
    StoreIndicator,
    'data' | 'currentLimit' | 'lastLivePoint' | 'dataVersion'
  >,
  data: readonly IndicatorDataPoint[],
): void {
  indicator.data = markRaw(Array.isArray(data) ? [...data] : []);
  indicator.currentLimit = indicator.data.length;
  indicator.lastLivePoint = indicator.data.at(-1) ?? null;
  indicator.dataVersion = (indicator.dataVersion || 0) + 1;
}

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

export function mergeRecoveredIndicatorData(
  existing: readonly IndicatorDataPoint[],
  recovered: readonly IndicatorDataPoint[],
  live: readonly IndicatorDataPoint[],
): IndicatorDataPoint[] {
  // Recovery corrects old duplicates; samples received during the request win.
  const history = mergeIndicatorData(recovered, existing, null);
  const merged = new Map(history.map((point) => [point.timestamp_ms, point]));
  for (const point of live) {
    merged.set(point.timestamp_ms, {
      ...merged.get(point.timestamp_ms),
      ...point,
    });
  }
  return [...merged.values()].sort(
    (left, right) => left.timestamp_ms - right.timestamp_ms,
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

// Retain live history for later recovery without triggering a full series redraw.
export function retainLivePoint(
  indicator: Pick<StoreIndicator, 'data' | 'lastLivePoint'>,
  point: IndicatorDataPoint | null,
): IndicatorDataPoint | null {
  if (!point) return null;
  indicator.lastLivePoint = point;
  const data = indicator.data;
  const last = data.at(-1);
  if (last?.timestamp_ms === point.timestamp_ms) {
    data[data.length - 1] = point;
  } else if (!last || last.timestamp_ms < point.timestamp_ms) {
    data.push(point);
  }
  return point;
}
