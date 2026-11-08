import { designTokens } from '@/design/tokens';
import type { BacktestClosedTrade } from '@/types/backtesterContracts';
import { isFiniteNumber, isRecord } from '@/types/transportValues';
import { anchorTimestamp, type LoadedCandleRange } from './backtestOverlay';
import type { ChartProtectiveLineSegment } from './protectiveLinesPrimitive';

interface PendingLimit {
  id: string;
  startMs: number;
  price: number;
}

const terminalOutcomes = new Set([
  'filled',
  'cancel',
  'expired',
  'replaced',
  'gap_expired',
  'schedule_cancelled',
  'constraint_cancelled',
  'reduce_only_cancelled',
  'oco_cancelled',
  'stop_cancelled',
  'run_end_expired',
]);

function segment(
  id: string,
  startMs: number,
  endMs: number,
  price: number,
  range: LoadedCandleRange,
  pending: boolean,
): ChartProtectiveLineSegment[] {
  if (endMs < range.startMs || startMs > range.endMs) return [];
  return [
    {
      id,
      startTime: Math.floor(
        anchorTimestamp(
          Math.max(startMs, range.startMs),
          range.candleStartsMs,
        ) / 1000,
      ) as ChartProtectiveLineSegment['startTime'],
      endTime: Math.floor(
        anchorTimestamp(Math.min(endMs, range.endMs), range.candleStartsMs) /
          1000,
      ) as ChartProtectiveLineSegment['endTime'],
      price,
      color: pending
        ? designTokens.chart.pendingLimit
        : designTokens.chart.entry,
      dashed: pending,
    },
  ];
}

export function buildBacktestEntryLines(
  trades: readonly BacktestClosedTrade[],
  range: LoadedCandleRange,
): ChartProtectiveLineSegment[] {
  return trades.flatMap((trade) =>
    segment(
      `${trade.trade_id}:entry-price`,
      trade.entry_timestamp_ms,
      trade.exit_timestamp_ms,
      trade.entry_price,
      range,
      false,
    ),
  );
}

export function buildBacktestLimitLines(
  events: unknown,
  range: LoadedCandleRange,
  runEndMs: number,
): ChartProtectiveLineSegment[] {
  if (!Array.isArray(events)) return [];
  const active = new Map<string, PendingLimit>();
  const segments: ChartProtectiveLineSegment[] = [];
  function close(orderId: string, timestamp: number) {
    const order = active.get(orderId);
    if (!order) return;
    segments.push(
      ...segment(order.id, order.startMs, timestamp, order.price, range, true),
    );
    active.delete(orderId);
  }
  for (const [index, event] of events.entries()) {
    if (
      !isRecord(event) ||
      typeof event.order_id !== 'string' ||
      typeof event.outcome !== 'string' ||
      !isFiniteNumber(event.timestamp_ms)
    )
      continue;
    if (event.outcome === 'submit' || event.outcome === 'update') {
      close(event.order_id, event.timestamp_ms);
      if (!isFiniteNumber(event.limit_price) || event.limit_price <= 0)
        continue;
      active.set(event.order_id, {
        id: `${event.order_id}:limit:${index}`,
        startMs: event.timestamp_ms,
        price: event.limit_price,
      });
    } else if (terminalOutcomes.has(event.outcome)) {
      close(event.order_id, event.timestamp_ms);
    }
  }
  for (const id of active.keys()) close(id, runEndMs);
  return segments;
}
