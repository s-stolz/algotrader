import { markRaw } from 'vue';
import type { IndicatorDataPoint, IndicatorInfo } from '@/types/contracts';
import type { IndicatorParameterUpdate, StoreIndicator } from './types';
import { createParameterMap, createStyles } from './configuration';
import { INITIAL_INDICATOR_LIMIT } from './historyCoverage';

export function createIndicator(
  _id: string,
  info: IndicatorInfo,
  indicatorData: IndicatorDataPoint[],
  indicatorId: number,
  paneIndex: number,
  providedParameters: IndicatorParameterUpdate = {},
): StoreIndicator {
  return {
    _id,
    indicatorId,
    info: { ...info },
    paneIndex,
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
}
