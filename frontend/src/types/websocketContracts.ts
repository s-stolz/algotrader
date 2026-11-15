import {
  isHistoryEvent,
  type HistoryDownloadChanged,
  type HistoryDownloadsConnection,
} from './historyDownloadContracts';
import {
  isBacktestEventMessage,
  type BacktestEventMessage,
} from './backtestEventContracts';
import { type Candle, isCandle } from './candleContracts';
import {
  isRecord,
  isFiniteNumber,
  isNonEmptyString,
  isNullableString,
} from './transportValues';

export interface CandleUpdateMessage extends Candle {
  market_id: number;
  type: 'candleUpdate';
  symbol: string;
  timeframe: string;
}

export interface IndicatorUpdateMessage {
  market_id: number;
  type: 'indicatorUpdate';
  clientIndicatorId: string;
  streamId?: string;
  symbol?: string;
  timeframe?: string;
  indicatorId?: number;
  timestamp_ms: number;
  values: Record<string, number | null>;
  replay?: boolean;
}

export interface CandleSubscribedMessage {
  market_id: number;
  type: 'subscribed';
  symbol?: string;
  timeframe: string;
}

export interface IndicatorSubscribedMessage {
  market_id: number;
  type: 'indicatorSubscribed';
  symbol?: string;
  timeframe: string;
  indicatorId: number;
  clientIndicatorId: string;
  streamId?: string | null;
}

export interface IndicatorUnsubscribedMessage {
  market_id: number;
  type: 'indicatorUnsubscribed';
  symbol?: string;
  timeframe: string;
  indicatorId: number;
  clientIndicatorId: string;
}

export interface WebSocketErrorMessage {
  type: 'error';
  error: string;
}

export type WebSocketControlMessage =
  | CandleSubscribedMessage
  | IndicatorSubscribedMessage
  | IndicatorUnsubscribedMessage
  | WebSocketErrorMessage;

export type WebSocketInboundMessage =
  | HistoryDownloadChanged
  | HistoryDownloadsConnection
  | BacktestEventMessage
  | CandleUpdateMessage
  | IndicatorUpdateMessage
  | WebSocketControlMessage;

function isIndicatorValueRecord(
  value: unknown,
): value is Record<string, number | null> {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (entry) => entry === null || isFiniteNumber(entry),
    )
  );
}

export function isCandleUpdateMessage(
  value: unknown,
): value is CandleUpdateMessage {
  return (
    isRecord(value) &&
    value.type === 'candleUpdate' &&
    Number.isInteger(value.market_id) &&
    Number(value.market_id) > 0 &&
    isNonEmptyString(value.symbol) &&
    isNonEmptyString(value.timeframe) &&
    isCandle(value)
  );
}

export function isIndicatorUpdateMessage(
  value: unknown,
): value is IndicatorUpdateMessage {
  return (
    isRecord(value) &&
    value.type === 'indicatorUpdate' &&
    Number.isInteger(value.market_id) &&
    Number(value.market_id) > 0 &&
    isNonEmptyString(value.clientIndicatorId) &&
    isFiniteNumber(value.timestamp_ms) &&
    value.timestamp_ms > 0 &&
    isIndicatorValueRecord(value.values) &&
    (value.replay === undefined || typeof value.replay === 'boolean') &&
    (!('streamId' in value) ||
      value.streamId === undefined ||
      typeof value.streamId === 'string') &&
    (!('symbol' in value) ||
      value.symbol === undefined ||
      typeof value.symbol === 'string') &&
    (!('timeframe' in value) ||
      value.timeframe === undefined ||
      typeof value.timeframe === 'string') &&
    (!('indicatorId' in value) ||
      value.indicatorId === undefined ||
      isFiniteNumber(value.indicatorId))
  );
}

export function isCandleSubscribedMessage(
  value: unknown,
): value is CandleSubscribedMessage {
  return (
    isRecord(value) &&
    value.type === 'subscribed' &&
    Number.isInteger(value.market_id) &&
    Number(value.market_id) > 0 &&
    (value.symbol === undefined || isNonEmptyString(value.symbol)) &&
    isNonEmptyString(value.timeframe)
  );
}

export function isIndicatorSubscribedMessage(
  value: unknown,
): value is IndicatorSubscribedMessage {
  return (
    isRecord(value) &&
    value.type === 'indicatorSubscribed' &&
    Number.isInteger(value.market_id) &&
    Number(value.market_id) > 0 &&
    (value.symbol === undefined || isNonEmptyString(value.symbol)) &&
    isNonEmptyString(value.timeframe) &&
    isFiniteNumber(value.indicatorId) &&
    isNonEmptyString(value.clientIndicatorId) &&
    (!('streamId' in value) ||
      value.streamId === undefined ||
      isNullableString(value.streamId))
  );
}

export function isIndicatorUnsubscribedMessage(
  value: unknown,
): value is IndicatorUnsubscribedMessage {
  return (
    isRecord(value) &&
    value.type === 'indicatorUnsubscribed' &&
    Number.isInteger(value.market_id) &&
    Number(value.market_id) > 0 &&
    (value.symbol === undefined || isNonEmptyString(value.symbol)) &&
    isNonEmptyString(value.timeframe) &&
    isFiniteNumber(value.indicatorId) &&
    isNonEmptyString(value.clientIndicatorId)
  );
}

export function isWebSocketErrorMessage(
  value: unknown,
): value is WebSocketErrorMessage {
  return (
    isRecord(value) && value.type === 'error' && isNonEmptyString(value.error)
  );
}

export function isWebSocketControlMessage(
  value: unknown,
): value is WebSocketControlMessage {
  return (
    isCandleSubscribedMessage(value) ||
    isIndicatorSubscribedMessage(value) ||
    isIndicatorUnsubscribedMessage(value) ||
    isWebSocketErrorMessage(value)
  );
}

export function isWebSocketInboundMessage(
  value: unknown,
): value is WebSocketInboundMessage {
  return (
    isHistoryEvent(value) ||
    isBacktestEventMessage(value) ||
    isCandleUpdateMessage(value) ||
    isIndicatorUpdateMessage(value) ||
    isWebSocketControlMessage(value)
  );
}
