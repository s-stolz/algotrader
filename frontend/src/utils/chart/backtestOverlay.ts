import type { BacktestClosedTrade } from '@/types/backtesterContracts';

import type {
  ChartProtectiveLineSegment,
  ChartSeriesMarker,
} from './ChartManager';

export interface LoadedCandleRange {
  startMs: number;
  endMs: number;
}

export const ENTRY_MARKER_COLOR = '#16a34a';
export const EXIT_MARKER_COLOR = '#dc2626';
export const STOP_LOSS_LINE_COLOR = '#dc2626';
export const TAKE_PROFIT_LINE_COLOR = '#2563eb';

function timestampToChartTime(timestampMs: number): ChartSeriesMarker['time'] {
  return Math.floor(timestampMs / 1000) as ChartSeriesMarker['time'];
}

function formatTradePrice(price: number): string {
  return String(price);
}

function isTimestampInRange(timestampMs: number, range: LoadedCandleRange): boolean {
  return timestampMs >= range.startMs && timestampMs <= range.endMs;
}

export function buildBacktestTradeMarkers(
  trades: readonly BacktestClosedTrade[],
  range: LoadedCandleRange,
): ChartSeriesMarker[] {
  const markers: ChartSeriesMarker[] = [];

  for (const trade of trades) {
    if (isTimestampInRange(trade.entry_timestamp_ms, range)) {
      markers.push({
        id: `${trade.trade_id}:entry`,
        time: timestampToChartTime(trade.entry_timestamp_ms),
        position: 'belowBar',
        shape: 'arrowUp',
        color: ENTRY_MARKER_COLOR,
        text: `Buy @ ${formatTradePrice(trade.entry_price)}`,
      });
    }

    if (isTimestampInRange(trade.exit_timestamp_ms, range)) {
      markers.push({
        id: `${trade.trade_id}:exit`,
        time: timestampToChartTime(trade.exit_timestamp_ms),
        position: 'aboveBar',
        shape: 'arrowDown',
        color: EXIT_MARKER_COLOR,
        text: `Sell @ ${formatTradePrice(trade.exit_price)}`,
      });
    }
  }

  return markers.sort((left, right) => Number(left.time) - Number(right.time));
}

export function buildBacktestProtectiveLineSegments(
  trades: readonly BacktestClosedTrade[],
): ChartProtectiveLineSegment[] {
  const segments: ChartProtectiveLineSegment[] = [];

  for (const trade of trades) {
    const startTime = timestampToChartTime(trade.entry_timestamp_ms);
    const endTime = timestampToChartTime(trade.exit_timestamp_ms);

    if (trade.stop_loss_price !== null) {
      segments.push({
        id: `${trade.trade_id}:stop-loss`,
        startTime,
        endTime,
        price: trade.stop_loss_price,
        color: STOP_LOSS_LINE_COLOR,
      });
    }

    if (trade.take_profit_price !== null) {
      segments.push({
        id: `${trade.trade_id}:take-profit`,
        startTime,
        endTime,
        price: trade.take_profit_price,
        color: TAKE_PROFIT_LINE_COLOR,
      });
    }
  }

  return segments;
}
