import { defineStore } from 'pinia';
import { computed, markRaw, reactive, ref } from 'vue';

import { requestIndicator as requestIndicatorFromApi } from '@/api/indicatorClient';
import type {
  IndicatorDataPoint,
  IndicatorInfo,
  IndicatorRequestBody,
  IndicatorUpdateMessage,
} from '@/types/contracts';
import { wsService } from '@/utils/websocketService';

import {
  applyParameterUpdates,
  createParameterMap,
  createStyles,
  extractParameterValues,
} from './indicators/configuration';
import {
  mergeIndicatorData,
  mergeLivePoint,
  trimDataToRange,
} from './indicators/historyData';
import {
  INITIAL_INDICATOR_LIMIT,
  applyCoverageTarget,
  buildLatestQuery,
  getBatchSize,
  getLoadedCandleRange,
  resetIndicatorHistoryState,
  runCoverageBackfill,
} from './indicators/historyCoverage';
import { toClientQuery, toSubscriptionPayload } from './indicators/requests';
import type {
  IndicatorCoverageOptions,
  IndicatorInfoMessage,
  IndicatorLiveSubscription,
  IndicatorLiveSubscriptionInput,
  IndicatorLoadedCandleRange,
  IndicatorParameterMap,
  IndicatorParameterUpdate,
  IndicatorStoreQuery,
  StoreIndicator,
} from './indicators/types';

export type {
  IndicatorParameterEntry,
  IndicatorParameterMap,
  IndicatorParameterUpdate,
  IndicatorParameterValues,
  IndicatorStyles,
  IndicatorLoadedCandleRange,
  IndicatorCoverageOptions,
  IndicatorStoreQuery,
  StoreIndicator,
} from './indicators/types';

export const useIndicatorsStore = defineStore('indicators', () => {
  const indicators = reactive(new Map<string, StoreIndicator>());
  const paneCount = ref(1);
  const liveSubscriptions = reactive(
    new Map<string, IndicatorLiveSubscription>(),
  );
  const all = computed(() => Array.from(indicators.values()));
  const defaultCoverageOptions = ref<IndicatorCoverageOptions | null>(null);

  function getById(_id: string): StoreIndicator | undefined {
    return indicators.get(_id);
  }

  function exists(_id: string): boolean {
    return indicators.has(_id);
  }

  function resetHistoryFlags(): void {
    for (const indicator of all.value) {
      resetIndicatorHistoryState(indicator, true);
    }
  }

  function configureHistoryCoverage(
    options: IndicatorCoverageOptions | null,
  ): void {
    defaultCoverageOptions.value = options;
  }

  function resolveCoverageOptions(
    options: IndicatorCoverageOptions = {},
  ): IndicatorCoverageOptions {
    return {
      ...(defaultCoverageOptions.value ?? {}),
      ...options,
    };
  }

  function trimIndicatorToRange(
    _id: string,
    range: IndicatorLoadedCandleRange | null,
  ): void {
    const indicator = indicators.get(_id);
    if (!indicator || !range) return;

    updateIndicatorData(_id, trimDataToRange(indicator.data, range));
  }

  function requestAllIndicators(
    symbol: string | null | undefined,
    timeframe: string | null | undefined,
    exchange: string | null = null,
    options: IndicatorCoverageOptions = {},
  ): void {
    if (!symbol || !timeframe) return;

    const coverageOptions = resolveCoverageOptions(options);
    const batchSize = getBatchSize(coverageOptions);

    for (const indicator of all.value) {
      const queryParams: IndicatorStoreQuery = {
        symbol,
        timeframe,
        limit: batchSize,
      };
      if (exchange) {
        queryParams.exchange = exchange;
      }

      const body: IndicatorRequestBody = {
        parameters: extractParameterValues(indicator.parameters),
      };

      void requestIndicator(
        indicator._id,
        indicator.indicatorId,
        queryParams,
        body,
        coverageOptions,
      );
    }
  }

  async function ensureCoverageForAll(
    symbol: string | null | undefined,
    timeframe: string | null | undefined,
    exchange: string | null = null,
    options: IndicatorCoverageOptions = {},
  ): Promise<void> {
    if (!symbol || !timeframe) return;

    const coverageOptions = resolveCoverageOptions(options);
    await Promise.all(
      all.value.map((indicator) =>
        ensureCoverageForIndicator(
          indicator._id,
          symbol,
          timeframe,
          exchange,
          coverageOptions,
        ),
      ),
    );
  }

  async function fetchOlderForAll(
    symbol: string | null | undefined,
    timeframe: string | null | undefined,
    exchange: string | null = null,
    batchSize = INITIAL_INDICATOR_LIMIT,
  ): Promise<void> {
    await ensureCoverageForAll(symbol, timeframe, exchange, { batchSize });
  }

  async function requestIndicator(
    _id: string | null | undefined,
    indicatorId: number,
    query: IndicatorStoreQuery,
    body: IndicatorRequestBody = {},
    options: IndicatorCoverageOptions = {},
  ): Promise<string | null> {
    const coverageOptions = resolveCoverageOptions(options);
    const clientQuery = toClientQuery(buildLatestQuery(query, coverageOptions));
    if (!clientQuery) return null;

    const existingIndicator = _id ? indicators.get(_id) : undefined;
    const generation = existingIndicator
      ? existingIndicator.historyGeneration + 1
      : null;
    if (existingIndicator) {
      resetIndicatorHistoryState(existingIndicator, true);
    }

    if (_id && liveSubscriptions.has(_id)) {
      await unsubscribeIndicatorLive(_id);
    }

    try {
      const response = await requestIndicatorFromApi(
        indicatorId,
        clientQuery,
        body,
      );
      if (
        _id &&
        generation !== null &&
        indicators.get(_id)?.historyGeneration !== generation
      ) {
        return null;
      }

      const localId = handleMessageIndicatorInfo({
        _id,
        indicatorId,
        ...response.data,
      });

      const activeId = localId || _id || null;
      const indicator = activeId ? indicators.get(activeId) : undefined;

      if (activeId && indicator) {
        const loadedRange = getLoadedCandleRange(coverageOptions);
        trimIndicatorToRange(activeId, loadedRange);

        await subscribeIndicatorLive(activeId, {
          symbol: clientQuery.symbol,
          timeframe: clientQuery.timeframe,
          exchange: clientQuery.exchange || null,
          indicatorId: indicator.indicatorId,
          parameters: extractParameterValues(indicator.parameters),
        });

        void ensureCoverageForIndicator(
          activeId,
          clientQuery.symbol,
          clientQuery.timeframe,
          clientQuery.exchange || null,
          coverageOptions,
        );
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
      const response = await requestIndicatorFromApi(
        indicatorId,
        clientQuery,
        body,
      );
      const mergedData = mergeIndicatorData(
        indicator.data,
        response.data.indicator_data,
        null,
      );
      updateIndicatorData(_id, mergedData);
    } catch (error) {
      console.error('Failed to prepend indicator data', error);
    }
  }

  async function ensureCoverageForIndicator(
    _id: string,
    symbol: string,
    timeframe: string,
    exchange: string | null,
    options: IndicatorCoverageOptions,
  ): Promise<void> {
    const indicator = indicators.get(_id);
    const range = getLoadedCandleRange(options);
    if (!indicator || !range || !indicator.data.length) return;

    applyCoverageTarget(indicator, range);
    trimIndicatorToRange(_id, range);

    if (indicator.historyExhausted) return;
    if (indicator.isBackfilling) {
      await indicator.activeBackfillPromise;
      return;
    }

    const generation = indicator.historyGeneration;
    indicator.isBackfilling = true;
    const promise = runCoverageBackfill(
      { getById, updateIndicatorData },
      _id,
      symbol,
      timeframe,
      exchange,
      options,
      generation,
    );
    indicator.activeBackfillPromise = promise;
    await promise;
  }

  function handleMessageIndicatorInfo(
    indicatorResponse: IndicatorInfoMessage,
  ): string | null {
    const {
      _id,
      indicatorId,
      indicator_info: indicatorInfo,
      indicator_data: indicatorData,
    } = indicatorResponse;
    const isNewIndicatorRequest = _id === null || _id === undefined;
    let newLocalId = _id ?? null;

    if (isNewIndicatorRequest) {
      newLocalId = addIndicator(indicatorInfo, indicatorData, indicatorId);
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
      historyGeneration: 0,
      isBackfilling: false,
      historyExhausted: false,
      targetOldestTimestampMs: null,
      targetNewestTimestampMs: null,
      nextBackfillEndMs: null,
      activeBackfillPromise: null,
    };

    indicators.set(_id, indicator);

    return _id;
  }

  function updateIndicatorData(
    _id: string,
    newData: IndicatorDataPoint[],
  ): void {
    const indicator = indicators.get(_id);

    if (!indicator) return;

    indicator.data = markRaw(Array.isArray(newData) ? [...newData] : []);
    indicator.currentLimit = indicator.data.length;
    indicator.lastLivePoint = indicator.data.length
      ? indicator.data[indicator.data.length - 1]
      : null;
    indicator.dataVersion = (indicator.dataVersion || 0) + 1;
  }

  function handleLiveUpdate(
    message: IndicatorUpdateMessage | null | undefined,
  ): IndicatorDataPoint | null {
    if (!message || message.type !== 'indicatorUpdate') return null;

    const _id = message.clientIndicatorId;
    const indicator = indicators.get(_id);
    if (!indicator) return null;

    const point = mergeLivePoint(indicator.lastLivePoint, message);
    if (point) indicator.lastLivePoint = point;
    return point;
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
    if (
      !_id ||
      !symbol ||
      !timeframe ||
      indicatorId === null ||
      indicatorId === undefined
    )
      return;

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
      await wsService.send(
        'subscribeIndicator',
        toSubscriptionPayload(payload),
      );
    } catch (error) {
      console.error('Failed to subscribe indicator stream:', error);
    }
  }

  async function unsubscribeIndicatorLive(_id: string): Promise<void> {
    const payload = liveSubscriptions.get(_id);
    if (!payload) return;

    try {
      await wsService.send(
        'unsubscribeIndicator',
        toSubscriptionPayload(payload),
      );
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
        await wsService.send(
          'unsubscribeIndicator',
          toSubscriptionPayload(payload),
        );
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

    return applyParameterUpdates(indicator.parameters, newParameters);
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

  function updateIndicatorPaneElement(
    _id: string,
    paneHtmlElement: HTMLElement | null,
  ): void {
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
    configureHistoryCoverage,
    resetHistoryFlags,
    requestAllIndicators,
    ensureCoverageForAll,
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
