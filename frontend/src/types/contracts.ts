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

export type TimeframeCode = typeof TIMEFRAME_CODES[number];

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

export interface Candle {
  timestamp_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartCandle extends Candle {
  time: number;
}

export interface CandleFetchOptions {
  startMs?: number | null;
  endMs?: number | null;
  limit?: number | null;
  exchange?: string | null;
}

export interface CandleBatchPayload {
  symbol: string;
  exchange?: string | null;
  candles: Candle[];
}

export interface CandleBatchResponse {
  status: string;
  added_candles: number;
  total_candles: number;
}

export interface AvailableIndicator {
  id: number;
  name: string;
}

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export interface JsonObject {
  [key: string]: JsonValue;
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

export type UploadColumnMapping = Record<number, UploadColumnField | '' | null | undefined>;
export type UploadFieldToIndexMapping = Partial<Record<UploadColumnField, number>>;
export type UploadProgressCallback = (progress: number, rowCount: number) => void;

export interface CandleUpdateMessage extends Candle {
  type: 'candleUpdate';
  symbol: string;
  timeframe: string;
}

export interface IndicatorUpdateMessage {
  type: 'indicatorUpdate';
  clientIndicatorId: string;
  streamId?: string;
  symbol?: string;
  timeframe?: string;
  indicatorId?: number;
  timestamp_ms: number;
  values: Record<string, number | null>;
}

const TIMEFRAME_CODE_SET: ReadonlySet<string> = new Set(TIMEFRAME_CODES);

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isTimeframeCode(value: unknown): value is TimeframeCode {
  return typeof value === 'string' && TIMEFRAME_CODE_SET.has(value);
}

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isJsonValue(value: unknown): value is JsonValue {
  if (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return true;
  }

  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }

  if (isRecord(value)) {
    return Object.values(value).every(isJsonValue);
  }

  return false;
}

function isJsonObject(value: unknown): value is JsonObject {
  return isRecord(value) && Object.values(value).every(isJsonValue);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || isFiniteNumber(value);
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

export function isMarketCreateResponse(value: unknown): value is MarketCreateResponse {
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
    (isFiniteNumber(value.deleted_count) || isMarketDeleteSummary(value.deleted_count))
  );
}

function isMarketDeleteSummary(value: unknown): value is MarketDeleteSummary {
  return (
    isRecord(value) &&
    typeof value.market_deleted === 'boolean' &&
    isFiniteNumber(value.deleted_candles)
  );
}

export function isCandle(value: unknown): value is Candle {
  if (!isRecord(value)) {
    return false;
  }

  if (
    !isFiniteNumber(value.timestamp_ms) ||
    value.timestamp_ms <= 0 ||
    !isFiniteNumber(value.open) ||
    !isFiniteNumber(value.high) ||
    !isFiniteNumber(value.low) ||
    !isFiniteNumber(value.close) ||
    !isFiniteNumber(value.volume)
  ) {
    return false;
  }

  return (
    value.high >= Math.max(value.low, value.open, value.close) &&
    value.low <= Math.min(value.open, value.close)
  );
}

export function isCandleArray(value: unknown): value is Candle[] {
  return Array.isArray(value) && value.every(isCandle);
}

export function isChartCandle(value: unknown): value is ChartCandle {
  return isCandle(value) && isRecord(value) && isFiniteNumber(value.time);
}

export function toChartCandle(candle: Candle): ChartCandle {
  return {
    ...candle,
    time: Math.floor(candle.timestamp_ms / 1000),
  };
}

export function isCandleBatchResponse(value: unknown): value is CandleBatchResponse {
  return (
    isRecord(value) &&
    isNonEmptyString(value.status) &&
    isFiniteNumber(value.added_candles) &&
    isFiniteNumber(value.total_candles)
  );
}

export function isAvailableIndicator(value: unknown): value is AvailableIndicator {
  return (
    isRecord(value) &&
    isFiniteNumber(value.id) &&
    isNonEmptyString(value.name)
  );
}

export function isAvailableIndicatorArray(value: unknown): value is AvailableIndicator[] {
  return Array.isArray(value) && value.every(isAvailableIndicator);
}

function isIndicatorOutputMetadata(value: unknown): value is IndicatorOutputMetadata {
  if (!isRecord(value)) {
    return false;
  }

  if ('type' in value && value.type !== undefined && typeof value.type !== 'string') {
    return false;
  }

  if ('plotOptions' in value && value.plotOptions !== undefined && !isJsonObject(value.plotOptions)) {
    return false;
  }

  return Object.values(value).every((entry) => entry === undefined || isJsonValue(entry));
}

function isIndicatorOutputMap(value: unknown): value is Record<string, IndicatorOutputMetadata> {
  return isRecord(value) && Object.values(value).every(isIndicatorOutputMetadata);
}

function isIndicatorParameterMap(value: unknown): value is Record<string, JsonObject> {
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

export function isIndicatorDataPoint(value: unknown): value is IndicatorDataPoint {
  if (!isRecord(value) || !isFiniteNumber(value.timestamp_ms) || value.timestamp_ms <= 0) {
    return false;
  }

  return Object.entries(value).every(([key, entry]) => (
    key === 'timestamp_ms' ||
    entry === null ||
    typeof entry === 'number' ||
    typeof entry === 'string'
  ));
}

export function isIndicatorResponse(value: unknown): value is IndicatorResponse {
  if (!isRecord(value) || !isRecord(value.data)) {
    return false;
  }

  return (
    isIndicatorInfo(value.data.indicator_info) &&
    Array.isArray(value.data.indicator_data) &&
    value.data.indicator_data.every(isIndicatorDataPoint)
  );
}

export function isStoredCurrentMarket(value: unknown): value is StoredCurrentMarket {
  return (
    isRecord(value) &&
    isNullableString(value.exchange) &&
    isNullableString(value.market_type) &&
    isNullableNumber(value.min_move) &&
    isNullableString(value.symbol) &&
    isNullableNumber(value.symbol_id)
  );
}

export function isStoredCurrentTimeframe(value: unknown): value is StoredCurrentTimeframe {
  return (
    isRecord(value) &&
    isTimeframeCode(value.label) &&
    isTimeframeCode(value.value)
  );
}

function isIndicatorValueRecord(value: unknown): value is Record<string, number | null> {
  return isRecord(value) && Object.values(value).every((entry) => entry === null || isFiniteNumber(entry));
}

export function isCandleUpdateMessage(value: unknown): value is CandleUpdateMessage {
  return (
    isRecord(value) &&
    value.type === 'candleUpdate' &&
    isNonEmptyString(value.symbol) &&
    isNonEmptyString(value.timeframe) &&
    isCandle(value)
  );
}

export function isIndicatorUpdateMessage(value: unknown): value is IndicatorUpdateMessage {
  return (
    isRecord(value) &&
    value.type === 'indicatorUpdate' &&
    isNonEmptyString(value.clientIndicatorId) &&
    isFiniteNumber(value.timestamp_ms) &&
    value.timestamp_ms > 0 &&
    isIndicatorValueRecord(value.values) &&
    (!('streamId' in value) || value.streamId === undefined || typeof value.streamId === 'string') &&
    (!('symbol' in value) || value.symbol === undefined || typeof value.symbol === 'string') &&
    (!('timeframe' in value) || value.timeframe === undefined || typeof value.timeframe === 'string') &&
    (!('indicatorId' in value) || value.indicatorId === undefined || isFiniteNumber(value.indicatorId))
  );
}
