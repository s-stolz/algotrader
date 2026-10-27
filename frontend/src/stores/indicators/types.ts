import type {
  IndicatorDataPoint,
  IndicatorInfo,
  JsonObject,
  JsonValue,
} from '@/types/contracts';

export type IndicatorParameterEntry = Record<string, JsonValue | undefined>;
export type IndicatorParameterMap = Record<string, IndicatorParameterEntry>;
export type IndicatorParameterUpdate = Record<
  string,
  JsonValue | IndicatorParameterEntry
>;
export type IndicatorParameterValues = JsonObject;
export type IndicatorStyles = Record<string, JsonObject>;

export interface IndicatorLoadedCandleRange {
  oldestTimestampMs: number;
  newestTimestampMs: number;
  exclusiveEndMs: number;
}

export interface IndicatorCoverageOptions {
  batchSize?: number;
  getLoadedCandleRange?: () => IndicatorLoadedCandleRange | null;
}

export interface IndicatorStoreQuery {
  symbol?: string | null;
  timeframe?: string | null;
  exchange?: string | null;
  startMs?: number | null;
  start_ms?: number | null;
  endMs?: number | null;
  end_ms?: number | null;
  limit?: number | null;
}

export interface IndicatorLiveSubscription {
  symbol: string;
  timeframe: string;
  exchange: string | null;
  indicatorId: number;
  parameters: IndicatorParameterValues;
  clientIndicatorId: string;
}

export type IndicatorLiveSubscriptionInput = Omit<
  IndicatorLiveSubscription,
  'clientIndicatorId'
>;

export interface StoreIndicator {
  _id: string;
  indicatorId: number;
  info: IndicatorInfo;
  paneIndex: number;
  paneHtmlElement: HTMLElement | null;
  data: IndicatorDataPoint[];
  lastLivePoint: IndicatorDataPoint | null;
  dataVersion: number;
  parameters: IndicatorParameterMap;
  styles: IndicatorStyles;
  currentLimit: number;
  hasExpandedHistory: boolean;
  historyGeneration: number;
  isBackfilling: boolean;
  historyExhausted: boolean;
  targetOldestTimestampMs: number | null;
  targetNewestTimestampMs: number | null;
  nextBackfillEndMs: number | null;
  activeBackfillPromise: Promise<void> | null;
}

export interface IndicatorInfoMessage {
  _id?: string | null;
  indicatorId: number;
  indicator_info: IndicatorInfo;
  indicator_data: IndicatorDataPoint[];
}
