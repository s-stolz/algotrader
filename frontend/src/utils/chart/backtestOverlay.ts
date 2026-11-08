import { normalizeTimeframeCode, timeframeToMinutes } from '@/utils/timeframes';
import { designTokens } from '@/design/tokens';
import type { BacktestClosedTrade } from '@/types/backtesterContracts';

import type {
  ChartProtectiveLineSegment,
  ChartSeriesMarker,
} from './ChartManager';
import { marketPricePrecision } from './priceFormatting';

export interface LoadedCandleRange {
  startMs: number;
  endMs: number;
  candleStartsMs?: readonly number[];
}

export const BUY_MARKER_COLOR = designTokens.chart.buy;
export const SELL_MARKER_COLOR = designTokens.chart.sell;
export const STOP_LOSS_LINE_COLOR = designTokens.chart.stopLoss;
export const TAKE_PROFIT_LINE_COLOR = designTokens.chart.takeProfit;

type TradeMarkerAction = 'buy' | 'sell';

function timestampToChartTime(timestampMs: number): ChartSeriesMarker['time'] {
  return Math.floor(timestampMs / 1000) as ChartSeriesMarker['time'];
}

function formatTradePrice(
  price: number,
  minMove: number | null | undefined,
): string {
  if (!Number.isFinite(price)) {
    return String(price);
  }

  if (
    typeof minMove !== 'number' ||
    !Number.isFinite(minMove) ||
    minMove <= 0
  ) {
    return String(price);
  }

  return price.toFixed(marketPricePrecision(minMove));
}

function isTimestampInRange(
  timestampMs: number,
  range: LoadedCandleRange,
): boolean {
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
    shape: kind === 'exit' ? 'circle' : isBuy ? 'arrowUp' : 'arrowDown',
    color: isBuy ? BUY_MARKER_COLOR : SELL_MARKER_COLOR,
    text: `${isBuy ? 'Buy' : 'Sell'} @ ${formatTradePrice(price, minMove)}`,
  };
}

export function formatBacktestMarkerDetails(
  trade: BacktestClosedTrade,
  kind: 'entry' | 'exit',
  minMove?: number | null,
): string {
  const price = kind === 'entry' ? trade.entry_price : trade.exit_price;
  const action = kind === 'entry' ? 'Open' : 'Close';
  const details = `${action} ${trade.trade_direction} @ ${formatTradePrice(price, minMove)}`;
  if (kind === 'entry') return details;

  const pnl = trade.realized_pnl;
  return `${details} · Realized PnL: ${pnl > 0 ? '+' : ''}${pnl.toFixed(2)} account units`;
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
      markers.push(
        markerForAction(
          trade.trade_id,
          entryAction,
          'entry',
          trade.entry_timestamp_ms,
          trade.entry_price,
          minMove,
        ),
      );
    }

    if (isTimestampInRange(trade.exit_timestamp_ms, range)) {
      markers.push(
        markerForAction(
          trade.trade_id,
          exitAction,
          'exit',
          trade.exit_timestamp_ms,
          trade.exit_price,
          minMove,
        ),
      );
    }
  }

  for (const marker of markers) {
    marker.time = timestampToChartTime(
      anchorTimestamp(Number(marker.time) * 1000, range.candleStartsMs),
    );
  }
  return markers.sort((left, right) => Number(left.time) - Number(right.time));
}

export function buildBacktestProtectiveLineSegments(
  trades: readonly BacktestClosedTrade[],
  candleStartsMs?: readonly number[],
): ChartProtectiveLineSegment[] {
  const segments: ChartProtectiveLineSegment[] = [];

  for (const trade of trades) {
    const startTime = timestampToChartTime(
      anchorTimestamp(trade.entry_timestamp_ms, candleStartsMs),
    );
    const endTime = timestampToChartTime(
      anchorTimestamp(trade.exit_timestamp_ms, candleStartsMs),
    );

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

export function orderCandleRange(
  timestamps: readonly number[],
  timeframe: string,
): LoadedCandleRange | null {
  if (!timestamps.length) return null;
  const starts = [...timestamps].sort((a, b) => a - b);
  const last = starts[starts.length - 1];
  const end = new Date(last);
  if (normalizeTimeframeCode(timeframe) === 'MN1') {
    end.setUTCMonth(end.getUTCMonth() + 1);
  } else {
    end.setTime(last + timeframeToMinutes(timeframe) * 60_000);
  }
  return {
    startMs: starts[0],
    endMs: end.getTime() - 1,
    candleStartsMs: starts,
  };
}

export function anchorTimestamp(
  timestamp: number,
  starts?: readonly number[],
): number {
  if (!starts?.length || timestamp < starts[0]) return timestamp;
  let low = 0;
  let high = starts.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (starts[middle] <= timestamp) low = middle + 1;
    else high = middle;
  }
  return starts[low - 1];
}
