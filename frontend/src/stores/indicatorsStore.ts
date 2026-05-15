import { defineStore } from 'pinia';
import { computed, markRaw, reactive, ref } from 'vue';

import { requestIndicator as requestIndicatorFromApi } from '@/api/indicatorClient';
import type {
  IndicatorDataPoint,
  IndicatorInfo,
  IndicatorQuery,
  IndicatorRequestBody,
  IndicatorUpdateMessage,
  JsonObject,
  JsonValue,
} from '@/types/contracts';
import { type WebSocketSendPayload, wsService } from '@/utils/websocketService';

const INITIAL_INDICATOR_LIMIT = 500;

export type IndicatorParameterEntry = Record<string, JsonValue | undefined>;
export type IndicatorParameterMap = Record<string, IndicatorParameterEntry>;
export type IndicatorParameterUpdate = Record<string, JsonValue | IndicatorParameterEntry>;
export type IndicatorParameterValues = JsonObject;
export type IndicatorStyles = Record<string, JsonObject>;

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

interface IndicatorLiveSubscription {
  symbol: string;
  timeframe: string;
  exchange: string | null;
  indicatorId: number;
  parameters: IndicatorParameterValues;
  clientIndicatorId: string;
}

type IndicatorLiveSubscriptionInput = Omit<IndicatorLiveSubscription, 'clientIndicatorId'>;

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
}

interface IndicatorInfoMessage {
  _id?: string | null;
  indicatorId: number;
  indicator_info: IndicatorInfo;
  indicator_data: IndicatorDataPoint[];
}

function isParameterEntry(value: JsonValue | IndicatorParameterEntry): value is IndicatorParameterEntry {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function createParameterMap(
  info: IndicatorInfo,
  providedParameters: IndicatorParameterUpdate = {},
): IndicatorParameterMap {
  const finalParameters: IndicatorParameterMap = {};

  for (const [key, provided] of Object.entries(providedParameters)) {
    finalParameters[key] = isParameterEntry(provided)
      ? { ...provided }
      : { value: provided };
  }

  for (const [key, paramInfo] of Object.entries(info.parameters)) {
    const existing = finalParameters[key];

    if (!existing) {
      finalParameters[key] = {
        ...paramInfo,
        value: paramInfo.default,
      };
      continue;
    }

    finalParameters[key] = {
      ...paramInfo,
      ...existing,
    };

    if (finalParameters[key].value === undefined) {
      finalParameters[key].value = finalParameters[key].default;
    }
  }

  return finalParameters;
}

function createStyles(outputs: IndicatorInfo['outputs']): IndicatorStyles {
  const styles: IndicatorStyles = {};

  for (const [outputKey, output] of Object.entries(outputs)) {
    if (outputKey !== 'timestamp') {
      styles[outputKey] = output.plotOptions ? { ...output.plotOptions } : {};
    }
  }

  return styles;
}

function toClientQuery(query: IndicatorStoreQuery): IndicatorQuery | null {
  if (!query.symbol || !query.timeframe) {
    return null;
  }

  const clientQuery: IndicatorQuery = {
    symbol: query.symbol,
    timeframe: query.timeframe,
  };

  if (query.exchange !== undefined) {
    clientQuery.exchange = query.exchange;
  }
  if (query.startMs !== undefined || query.start_ms !== undefined) {
    clientQuery.startMs = query.startMs ?? query.start_ms ?? null;
  }
  if (query.endMs !== undefined || query.end_ms !== undefined) {
    clientQuery.endMs = query.endMs ?? query.end_ms ?? null;
  }
  if (query.limit !== undefined) {
    clientQuery.limit = query.limit;
  }

  return clientQuery;
}

function toSubscriptionPayload(subscription: IndicatorLiveSubscription): WebSocketSendPayload {
  return {
    symbol: subscription.symbol,
    timeframe: subscription.timeframe,
    exchange: subscription.exchange,
    indicatorId: subscription.indicatorId,
    parameters: subscription.parameters,
    clientIndicatorId: subscription.clientIndicatorId,
  };
}

export const useIndicatorsStore = defineStore('indicators', () => {
  const indicators = reactive(new Map<string, StoreIndicator>());
  const paneCount = ref(1);
  const liveSubscriptions = reactive(new Map<string, IndicatorLiveSubscription>());
  const all = computed(() => Array.from(indicators.values()));

  function getById(_id: string): StoreIndicator | undefined {
    return indicators.get(_id);
  }

  function exists(_id: string): boolean {
    return indicators.has(_id);
  }

  function extractParameterValues(parameters: IndicatorParameterMap): IndicatorParameterValues {
    const out: IndicatorParameterValues = {};

    for (const [key, parameter] of Object.entries(parameters)) {
      const value = parameter.value !== undefined ? parameter.value : parameter.default;
      if (value !== undefined) {
        out[key] = value;
      }
    }

    return out;
  }

  function resetHistoryFlags(): void {
    for (const indicator of all.value) {
      indicator.hasExpandedHistory = false;
      indicator.currentLimit = INITIAL_INDICATOR_LIMIT;
    }
  }

  function requestAllIndicators(
    symbol: string | null | undefined,
    timeframe: string | null | undefined,
    exchange: string | null = null,
  ): void {
    if (!symbol || !timeframe) return;

    for (const indicator of all.value) {
      if (indicator.hasExpandedHistory) continue;

      const queryParams: IndicatorStoreQuery = {
        symbol,
        timeframe,
        limit: indicator.currentLimit || INITIAL_INDICATOR_LIMIT,
      };
      if (exchange) {
        queryParams.exchange = exchange;
      }

      const body: IndicatorRequestBody = {
        parameters: extractParameterValues(indicator.parameters),
      };

      void requestIndicator(indicator._id, indicator.indicatorId, queryParams, body);
    }
  }

  async function fetchOlderForAll(
    symbol: string | null | undefined,
    timeframe: string | null | undefined,
    exchange: string | null = null,
    batchSize = 5000,
  ): Promise<void> {
    if (!symbol || !timeframe) return;

    for (const indicator of all.value) {
      if (!indicator.data.length) continue;
      indicator.hasExpandedHistory = true;

      const earliestTs = indicator.data[0].timestamp_ms;
      const queryParams: IndicatorStoreQuery = {
        symbol,
        timeframe,
        endMs: earliestTs,
        limit: batchSize,
      };
      if (exchange) {
        queryParams.exchange = exchange;
      }

      const body: IndicatorRequestBody = {
        parameters: extractParameterValues(indicator.parameters),
      };

      await requestIndicatorPrepend(indicator._id, indicator.indicatorId, queryParams, body);
    }
  }

  async function requestIndicator(
    _id: string | null | undefined,
    indicatorId: number,
    query: IndicatorStoreQuery,
    body: IndicatorRequestBody = {},
  ): Promise<string | null> {
    const clientQuery = toClientQuery(query);
    if (!clientQuery) return null;

    if (_id && liveSubscriptions.has(_id)) {
      await unsubscribeIndicatorLive(_id);
    }

    try {
      const response = await requestIndicatorFromApi(indicatorId, clientQuery, body);

      const localId = handleMessageIndicatorInfo({
        _id,
        indicatorId,
        ...response.data,
      });

      const activeId = localId || _id || null;
      const indicator = activeId ? indicators.get(activeId) : undefined;

      if (activeId && indicator) {
        await subscribeIndicatorLive(activeId, {
          symbol: clientQuery.symbol,
          timeframe: clientQuery.timeframe,
          exchange: clientQuery.exchange || null,
          indicatorId: indicator.indicatorId,
          parameters: extractParameterValues(indicator.parameters),
        });
      }

      return activeId;
    } catch (error) {
      console.error('Error fetching indicator:', error);
      return null;
    }
  }

  async function requestIndicatorPrepend(
    _id: string,
    indicatorId: number,
    query: IndicatorStoreQuery,
    body: IndicatorRequestBody = {},
  ): Promise<void> {
    const indicator = indicators.get(_id);
    const clientQuery = toClientQuery(query);

    if (!indicator || !indicator.data.length || !clientQuery) return;

    try {
      const response = await requestIndicatorFromApi(indicatorId, clientQuery, body);
      const mergedData = [...response.data.indicator_data, ...indicator.data];
      updateIndicatorData(_id, mergedData);
    } catch (error) {
      console.error('Failed to prepend indicator data', error);
    }
  }

  function handleMessageIndicatorInfo(indicatorResponse: IndicatorInfoMessage): string | null {
    const {
      _id,
      indicatorId,
      indicator_info: indicatorInfo,
      indicator_data: indicatorData,
    } = indicatorResponse;
    const isNewIndicatorRequest = _id === null || _id === undefined;
    let newLocalId = _id ?? null;

    if (isNewIndicatorRequest) {
      newLocalId = addIndicator(
        indicatorInfo,
        indicatorData,
        indicatorId,
      );
    } else {
      if (!indicators.has(_id)) {
        return null;
      }

      updateIndicatorData(_id, indicatorData);
    }

    return newLocalId;
  }

  function addIndicator(
    info: IndicatorInfo,
    indicatorData: IndicatorDataPoint[],
    indicatorId: number,
    providedParameters: IndicatorParameterUpdate = {},
  ): string {
    const _id = String(Date.now());
    const indicator: StoreIndicator = {
      _id,
      indicatorId,
      info: { ...info },
      paneIndex: info.overlay ? 0 : paneCount.value++,
      paneHtmlElement: null,
      data: markRaw([...indicatorData]),
      lastLivePoint: null,
      dataVersion: 0,
      parameters: createParameterMap(info, providedParameters),
      styles: createStyles(info.outputs || {}),
      currentLimit: indicatorData.length || INITIAL_INDICATOR_LIMIT,
      hasExpandedHistory: false,
    };

    indicators.set(_id, indicator);

    return _id;
  }

  function updateIndicatorData(_id: string, newData: IndicatorDataPoint[]): void {
    const indicator = indicators.get(_id);

    if (!indicator) return;

    indicator.data = markRaw(Array.isArray(newData) ? [...newData] : []);
    indicator.currentLimit = indicator.data.length;
    indicator.lastLivePoint = indicator.data.length ? indicator.data[indicator.data.length - 1] : null;
    indicator.dataVersion = (indicator.dataVersion || 0) + 1;
  }

  function handleLiveUpdate(message: IndicatorUpdateMessage | null | undefined): IndicatorDataPoint | null {
    if (!message || message.type !== 'indicatorUpdate') return null;

    const _id = message.clientIndicatorId;
    const indicator = indicators.get(_id);
    if (!indicator) return null;

    const timestampMs = Number(message.timestamp_ms);
    if (!Number.isFinite(timestampMs)) return null;

    const point: IndicatorDataPoint = { timestamp_ms: timestampMs, ...message.values };
    const lastLivePoint = indicator.lastLivePoint;

    if (!lastLivePoint) {
      indicator.lastLivePoint = point;
      return point;
    }

    if (Number(lastLivePoint.timestamp_ms) === timestampMs) {
      const merged: IndicatorDataPoint = { ...lastLivePoint, ...point };
      indicator.lastLivePoint = merged;
      return merged;
    }

    if (Number(lastLivePoint.timestamp_ms) < timestampMs) {
      indicator.lastLivePoint = point;
      return point;
    }

    return null;
  }

  async function subscribeIndicatorLive(
    _id: string,
    {
      symbol,
      timeframe,
      exchange = null,
      indicatorId,
      parameters = {},
    }: IndicatorLiveSubscriptionInput,
  ): Promise<void> {
    if (!_id || !symbol || !timeframe || indicatorId === null || indicatorId === undefined) return;

    const payload: IndicatorLiveSubscription = {
      symbol,
      timeframe,
      exchange,
      indicatorId,
      parameters,
      clientIndicatorId: _id,
    };

    liveSubscriptions.set(_id, payload);
    try {
      await wsService.send('subscribeIndicator', toSubscriptionPayload(payload));
    } catch (error) {
      console.error('Failed to subscribe indicator stream:', error);
    }
  }

  async function unsubscribeIndicatorLive(_id: string): Promise<void> {
    const payload = liveSubscriptions.get(_id);
    if (!payload) return;

    try {
      await wsService.send('unsubscribeIndicator', toSubscriptionPayload(payload));
    } catch (error) {
      console.error('Failed to unsubscribe indicator stream:', error);
    } finally {
      liveSubscriptions.delete(_id);
    }
  }

  async function unsubscribeAllLive(): Promise<void> {
    const subscriptions = Array.from(liveSubscriptions.entries());
    for (const [id, payload] of subscriptions) {
      try {
        await wsService.send('unsubscribeIndicator', toSubscriptionPayload(payload));
      } catch (error) {
        console.error('Failed to unsubscribe indicator stream:', error);
      } finally {
        liveSubscriptions.delete(id);
      }
    }
  }

  async function resubscribeAllLive(
    symbol: string | null | undefined,
    timeframe: string | null | undefined,
    exchange: string | null = null,
  ): Promise<void> {
    if (!symbol || !timeframe) return;

    await unsubscribeAllLive();
    for (const indicator of all.value) {
      await subscribeIndicatorLive(indicator._id, {
        symbol,
        timeframe,
        exchange,
        indicatorId: indicator.indicatorId,
        parameters: extractParameterValues(indicator.parameters),
      });
    }
  }

  function updateIndicatorParameters(
    _id: string,
    newParameters: IndicatorParameterUpdate,
  ): IndicatorParameterMap | null {
    const indicator = indicators.get(_id);

    if (!indicator) return null;

    for (const [key, paramVal] of Object.entries(newParameters)) {
      const parameter = indicator.parameters[key];
      if (!parameter) continue;

      if (isParameterEntry(paramVal)) {
        if ('value' in paramVal) {
          parameter.value = paramVal.value;
        }
      } else {
        parameter.value = paramVal;
      }
    }

    return indicator.parameters;
  }

  function removeIndicator(_id: string): void {
    const indicator = indicators.get(_id);
    if (!indicator) return;

    void unsubscribeIndicatorLive(_id);

    const paneIndex = indicator.paneIndex;
    if (paneIndex > 0) {
      updateIndicatorsPaneIndex(paneIndex);
    }

    indicators.delete(_id);
  }

  function updateIndicatorsPaneIndex(changedPaneIndex: number): void {
    for (const indicator of indicators.values()) {
      if (indicator.paneIndex > changedPaneIndex) {
        indicator.paneIndex--;
        indicator.paneHtmlElement = null;
      }
    }

    paneCount.value = Math.max(1, paneCount.value - 1);
  }

  function updateIndicatorPaneElement(_id: string, paneHtmlElement: HTMLElement | null): void {
    const indicator = indicators.get(_id);
    if (!indicator) return;

    indicator.paneHtmlElement = paneHtmlElement;
  }

  function clear(): void {
    void unsubscribeAllLive();
    indicators.clear();
    paneCount.value = 1;
  }

  return {
    indicators,
    paneCount,
    liveSubscriptions,
    all,
    getById,
    exists,
    resetHistoryFlags,
    requestAllIndicators,
    fetchOlderForAll,
    requestIndicator,
    requestIndicatorPrepend,
    handleMessageIndicatorInfo,
    addIndicator,
    updateIndicatorData,
    handleLiveUpdate,
    subscribeIndicatorLive,
    unsubscribeIndicatorLive,
    unsubscribeAllLive,
    resubscribeAllLive,
    updateIndicatorParameters,
    removeIndicator,
    updateIndicatorsPaneIndex,
    updateIndicatorPaneElement,
    clear,
    extractParameterValues,
    createStyles,
  };
});
