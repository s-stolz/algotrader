import {
  type JsonObject,
  type JsonValue,
  isRecord,
  isFiniteNumber,
  isNonEmptyString,
  isJsonValue,
  isJsonObject,
  isNullableString,
  isNullableNumber,
} from './transportValues';

export {
  type JsonPrimitive,
  type JsonValue,
  type JsonObject,
  isRecord,
  isFiniteNumber,
} from './transportValues';

export {
  type Candle,
  type ChartCandle,
  type CandleFetchOptions,
  type CandleBatchPayload,
  type CandleBatchResponse,
  isCandle,
  isCandleArray,
  isChartCandle,
  toChartCandle,
  isCandleBatchResponse,
} from './candleContracts';

export {
  type CandleUpdateMessage,
  type IndicatorUpdateMessage,
  type CandleSubscribedMessage,
  type IndicatorSubscribedMessage,
  type IndicatorUnsubscribedMessage,
  type WebSocketErrorMessage,
  type WebSocketControlMessage,
  type WebSocketInboundMessage,
  isCandleUpdateMessage,
  isIndicatorUpdateMessage,
  isCandleSubscribedMessage,
  isIndicatorSubscribedMessage,
  isIndicatorUnsubscribedMessage,
  isWebSocketErrorMessage,
  isWebSocketControlMessage,
  isWebSocketInboundMessage,
} from './websocketContracts';

export const TIMEFRAME_CODES = [
  'M1',
  'M2',
  'M3',
  'M4',
  'M5',
  'M10',
  'M15',
  'M30',
  'H1',
  'H4',
  'H12',
  'D1',
  'W1',
  'MN1',
] as const;

export type TimeframeCode = (typeof TIMEFRAME_CODES)[number];

export interface TimeframeOption {
  label: TimeframeCode;
  value: TimeframeCode;
}

export interface Market {
  symbol_id: number;
  symbol: string;
  exchange: string;
  market_type: string;
  min_move: number;
  timezone: string;
}

export interface MarketCreatePayload {
  symbol: string;
  exchange: string;
  market_type: string;
  min_move: number;
  timezone: string;
}

export interface MarketCreateResponse {
  symbol_id: number;
  status: string;
}

export interface MarketDeleteSummary {
  market_deleted: boolean;
  deleted_candles: number;
}

export interface DeleteResponse {
  status: string;
  deleted_count: number | MarketDeleteSummary;
}

export interface AvailableIndicator {
  id: number;
  name: string;
}

export interface IndicatorOutputMetadata {
  type?: string;
  plotOptions?: JsonObject;
  [key: string]: JsonValue | undefined;
}

export interface IndicatorInfo {
  id: number;
  indicator_id: string;
  name: string;
  overlay: boolean;
  inputs: string[];
  outputs: Record<string, IndicatorOutputMetadata>;
  parameters: Record<string, JsonObject>;
}

export interface IndicatorDataPoint {
  timestamp_ms: number;
  [key: string]: number | string | null;
}

export interface IndicatorResponse {
  data: {
    indicator_info: IndicatorInfo;
    indicator_data: IndicatorDataPoint[];
  };
}

export interface IndicatorQuery {
  symbol: string;
  timeframe: TimeframeCode | string;
  exchange?: string | null;
  startMs?: number | null;
  endMs?: number | null;
  limit?: number | null;
}

export interface IndicatorRequestBody {
  parameters?: Record<string, JsonValue>;
}

export interface StoredCurrentMarket {
  exchange: string | null;
  market_type: string | null;
  min_move: number | null;
  symbol: string | null;
  symbol_id: number | null;
}

export interface StoredCurrentTimeframe {
  label: TimeframeCode;
  value: TimeframeCode;
}

export type UploadColumnField =
  | 'timestamp'
  | 'date'
  | 'time'
  | 'open'
  | 'high'
  | 'low'
  | 'close'
  | 'volume';

export type UploadColumnMapping = Record<
  number,
  UploadColumnField | '' | null | undefined
>;

export type UploadFieldToIndexMapping = Partial<
  Record<UploadColumnField, number>
>;

export type UploadProgressCallback = (
  progress: number,
  rowCount: number,
) => void;

const TIMEFRAME_CODE_SET: ReadonlySet<string> = new Set(TIMEFRAME_CODES);

export function isTimeframeCode(value: unknown): value is TimeframeCode {
  return typeof value === 'string' && TIMEFRAME_CODE_SET.has(value);
}

export function isMarket(value: unknown): value is Market {
  return (
    isRecord(value) &&
    isFiniteNumber(value.symbol_id) &&
    isNonEmptyString(value.symbol) &&
    isNonEmptyString(value.exchange) &&
    isNonEmptyString(value.market_type) &&
    isFiniteNumber(value.min_move) &&
    isNonEmptyString(value.timezone)
  );
}

export function isMarketArray(value: unknown): value is Market[] {
  return Array.isArray(value) && value.every(isMarket);
}

export function isMarketCreateResponse(
  value: unknown,
): value is MarketCreateResponse {
  return (
    isRecord(value) &&
    isFiniteNumber(value.symbol_id) &&
    isNonEmptyString(value.status)
  );
}

export function isDeleteResponse(value: unknown): value is DeleteResponse {
  return (
    isRecord(value) &&
    isNonEmptyString(value.status) &&
    (isFiniteNumber(value.deleted_count) ||
      isMarketDeleteSummary(value.deleted_count))
  );
}

function isMarketDeleteSummary(value: unknown): value is MarketDeleteSummary {
  return (
    isRecord(value) &&
    typeof value.market_deleted === 'boolean' &&
    isFiniteNumber(value.deleted_candles)
  );
}

export function isAvailableIndicator(
  value: unknown,
): value is AvailableIndicator {
  return (
    isRecord(value) && isFiniteNumber(value.id) && isNonEmptyString(value.name)
  );
}

export function isAvailableIndicatorArray(
  value: unknown,
): value is AvailableIndicator[] {
  return Array.isArray(value) && value.every(isAvailableIndicator);
}

function isIndicatorOutputMetadata(
  value: unknown,
): value is IndicatorOutputMetadata {
  if (!isRecord(value)) {
    return false;
  }

  if (
    'type' in value &&
    value.type !== undefined &&
    typeof value.type !== 'string'
  ) {
    return false;
  }

  if (
    'plotOptions' in value &&
    value.plotOptions !== undefined &&
    !isJsonObject(value.plotOptions)
  ) {
    return false;
  }

  return Object.values(value).every(
    (entry) => entry === undefined || isJsonValue(entry),
  );
}

function isIndicatorOutputMap(
  value: unknown,
): value is Record<string, IndicatorOutputMetadata> {
  return (
    isRecord(value) && Object.values(value).every(isIndicatorOutputMetadata)
  );
}

function isIndicatorParameterMap(
  value: unknown,
): value is Record<string, JsonObject> {
  return isRecord(value) && Object.values(value).every(isJsonObject);
}

export function isIndicatorInfo(value: unknown): value is IndicatorInfo {
  return (
    isRecord(value) &&
    isFiniteNumber(value.id) &&
    isNonEmptyString(value.indicator_id) &&
    isNonEmptyString(value.name) &&
    typeof value.overlay === 'boolean' &&
    Array.isArray(value.inputs) &&
    value.inputs.every((input) => typeof input === 'string') &&
    isIndicatorOutputMap(value.outputs) &&
    isIndicatorParameterMap(value.parameters)
  );
}

export function isIndicatorDataPoint(
  value: unknown,
): value is IndicatorDataPoint {
  if (
    !isRecord(value) ||
    !isFiniteNumber(value.timestamp_ms) ||
    value.timestamp_ms <= 0
  ) {
    return false;
  }

  return Object.entries(value).every(
    ([key, entry]) =>
      key === 'timestamp_ms' ||
      entry === null ||
      typeof entry === 'number' ||
      typeof entry === 'string',
  );
}

export function isIndicatorResponse(
  value: unknown,
): value is IndicatorResponse {
  if (!isRecord(value) || !isRecord(value.data)) {
    return false;
  }

  return (
    isIndicatorInfo(value.data.indicator_info) &&
    Array.isArray(value.data.indicator_data) &&
    value.data.indicator_data.every(isIndicatorDataPoint)
  );
}

export function isStoredCurrentMarket(
  value: unknown,
): value is StoredCurrentMarket {
  return (
    isRecord(value) &&
    isNullableString(value.exchange) &&
    isNullableString(value.market_type) &&
    isNullableNumber(value.min_move) &&
    isNullableString(value.symbol) &&
    isNullableNumber(value.symbol_id)
  );
}

export function isStoredCurrentTimeframe(
  value: unknown,
): value is StoredCurrentTimeframe {
  return (
    isRecord(value) &&
    isTimeframeCode(value.label) &&
    isTimeframeCode(value.value)
  );
}
