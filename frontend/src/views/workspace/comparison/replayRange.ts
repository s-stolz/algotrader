import type {
  UTCTimestamp,
  LineData,
  WhitespaceData,
} from 'lightweight-charts';

export function extendReplayRange(
  points: LineData<UTCTimestamp>[],
  range?: { from: number; to: number },
): (LineData<UTCTimestamp> | WhitespaceData<UTCTimestamp>)[] {
  if (!range || !points.length) return points;
  const result: (LineData<UTCTimestamp> | WhitespaceData<UTCTimestamp>)[] = [
    ...points,
  ];
  const from = Math.floor(range.from / 1000) as UTCTimestamp;
  const to = Math.floor(range.to / 1000) as UTCTimestamp;
  if (from < points[0].time) result.unshift({ time: from });
  if (to > points[points.length - 1].time) result.push({ time: to });
  return result;
}
