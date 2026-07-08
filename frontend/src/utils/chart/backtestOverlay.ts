import type { BacktestClosedTrade } from '@/types/backtesterContracts';

import type {
  ChartProtectiveLineSegment,
  ChartSeriesMarker,
} from './ChartManager';
import { measurementPricePrecision } from './measurementOverlay';

export interface LoadedCandleRange {
  startMs: number;
  endMs: number;
}

export const BUY_MARKER_COLOR = '#00E676';
export const SELL_MARKER_COLOR = '#FF5252';
export const STOP_LOSS_LINE_COLOR = '#dc2626';
export const TAKE_PROFIT_LINE_COLOR = '#2563eb';

type TradeMarkerAction = 'buy' | 'sell';

function timestampToChartTime(timestampMs: number): ChartSeriesMarker['time'] {
  return Math.floor(timestampMs / 1000) as ChartSeriesMarker['time'];
}

function formatTradePrice(price: number, minMove: number | null | undefined): string {
  if (!Number.isFinite(price)) {
    return String(price);
  }

  if (typeof minMove !== 'number' || !Number.isFinite(minMove) || minMove <= 0) {
    return String(price);
  }

  return price.toFixed(measurementPricePrecision(minMove));
}

function isTimestampInRange(timestampMs: number, range: LoadedCandleRange): boolean {
  return timestampMs >= range.startMs && timestampMs <= range.endMs;
}

function markerForAction(
  tradeId: string,
  action: TradeMarkerAction,
  kind: 'entry' | 'exit',
  timestampMs: number,
  price: number,
  minMove?: number | null,
): ChartSeriesMarker {
  const isBuy = action === 'buy';

  return {
    id: `${tradeId}:${kind}`,
    time: timestampToChartTime(timestampMs),
    position: isBuy ? 'belowBar' : 'aboveBar',
    shape: isBuy ? 'arrowUp' : 'arrowDown',
    color: isBuy ? BUY_MARKER_COLOR : SELL_MARKER_COLOR,
    text: `${isBuy ? 'Buy' : 'Sell'} @ ${formatTradePrice(price, minMove)}`,
  };
}

export function buildBacktestTradeMarkers(
  trades: readonly BacktestClosedTrade[],
  range: LoadedCandleRange,
  minMove?: number | null,
): ChartSeriesMarker[] {
  const markers: ChartSeriesMarker[] = [];

  for (const trade of trades) {
    const entryAction = trade.trade_direction === 'long' ? 'buy' : 'sell';
    const exitAction = trade.trade_direction === 'long' ? 'sell' : 'buy';

    if (isTimestampInRange(trade.entry_timestamp_ms, range)) {
      markers.push(markerForAction(
        trade.trade_id,
        entryAction,
        'entry',
        trade.entry_timestamp_ms,
        trade.entry_price,
        minMove,
      ));
    }

    if (isTimestampInRange(trade.exit_timestamp_ms, range)) {
      markers.push(markerForAction(
        trade.trade_id,
        exitAction,
        'exit',
        trade.exit_timestamp_ms,
        trade.exit_price,
        minMove,
      ));
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
