import { requestIndicator as requestIndicatorFromApi } from '@/api/indicatorClient';
import type {
  IndicatorDataPoint,
  IndicatorRequestBody,
} from '@/types/contracts';
import { extractParameterValues } from './configuration';
import { mergeIndicatorData, trimDataToRange } from './historyData';
import { toClientQuery } from './requests';
import type {
  IndicatorCoverageOptions,
  IndicatorLoadedCandleRange,
  IndicatorStoreQuery,
  StoreIndicator,
} from './types';

export const INITIAL_INDICATOR_LIMIT = 500;

interface IndicatorCoverageContext {
  getById(id: string): StoreIndicator | undefined;
  updateIndicatorData(id: string, data: IndicatorDataPoint[]): void;
}

export function getBatchSize(options: IndicatorCoverageOptions): number {
  return options.batchSize ?? INITIAL_INDICATOR_LIMIT;
}

export function getLoadedCandleRange(
  options: IndicatorCoverageOptions,
): IndicatorLoadedCandleRange | null {
  const range = options.getLoadedCandleRange?.() ?? null;
  if (!range) return null;

  if (
    !Number.isFinite(range.oldestTimestampMs) ||
    !Number.isFinite(range.newestTimestampMs) ||
    !Number.isFinite(range.exclusiveEndMs)
  ) {
    return null;
  }

  return range;
}

export function resetIndicatorHistoryState(
  indicator: StoreIndicator,
  invalidateGeneration = false,
): void {
  indicator.hasExpandedHistory = false;
  indicator.currentLimit = INITIAL_INDICATOR_LIMIT;
  indicator.isBackfilling = false;
  indicator.historyExhausted = false;
  indicator.targetOldestTimestampMs = null;
  indicator.targetNewestTimestampMs = null;
  indicator.nextBackfillEndMs = null;
  indicator.activeBackfillPromise = null;
  if (invalidateGeneration) {
    indicator.historyGeneration += 1;
  }
}

export function applyCoverageTarget(
  indicator: StoreIndicator,
  range: IndicatorLoadedCandleRange,
): void {
  indicator.targetOldestTimestampMs =
    indicator.targetOldestTimestampMs === null
      ? range.oldestTimestampMs
      : Math.min(indicator.targetOldestTimestampMs, range.oldestTimestampMs);
  indicator.targetNewestTimestampMs =
    indicator.targetNewestTimestampMs === null
      ? range.newestTimestampMs
      : Math.max(indicator.targetNewestTimestampMs, range.newestTimestampMs);
}

export function buildLatestQuery(
  query: IndicatorStoreQuery,
  options: IndicatorCoverageOptions,
): IndicatorStoreQuery {
  const range = getLoadedCandleRange(options);
  const batchSize = getBatchSize(options);

  return {
    ...query,
    endMs: query.endMs ?? query.end_ms ?? range?.exclusiveEndMs ?? null,
    limit: query.limit ?? batchSize,
  };
}

export async function runCoverageBackfill(
  context: IndicatorCoverageContext,
  _id: string,
  symbol: string,
  timeframe: string,
  exchange: string | null,
  options: IndicatorCoverageOptions,
  generation: number,
): Promise<void> {
  try {
    while (true) {
      const indicator = context.getById(_id);
      const range = getLoadedCandleRange(options);
      if (!indicator || !range || indicator.historyGeneration !== generation)
        return;

      applyCoverageTarget(indicator, range);
      context.updateIndicatorData(_id, trimDataToRange(indicator.data, range));

      const current = context.getById(_id);
      if (!current || current.historyGeneration !== generation) return;
      if (current.historyExhausted || !current.data.length) return;

      const earliestTs = current.data[0].timestamp_ms;
      const targetOldestTs =
        current.targetOldestTimestampMs ?? range.oldestTimestampMs;
      if (earliestTs <= targetOldestTs) return;

      const endMs = Math.min(
        current.nextBackfillEndMs ?? earliestTs,
        earliestTs,
      );
      const queryParams: IndicatorStoreQuery = {
        symbol,
        timeframe,
        endMs,
        limit: getBatchSize(options),
      };
      if (exchange) {
        queryParams.exchange = exchange;
      }

      const body: IndicatorRequestBody = {
        parameters: extractParameterValues(current.parameters),
      };

      const response = await requestIndicatorFromApi(
        current.indicatorId,
        toClientQuery(queryParams)!,
        body,
      );

      const afterFetch = context.getById(_id);
      const latestRange = getLoadedCandleRange(options);
      if (
        !afterFetch ||
        !latestRange ||
        afterFetch.historyGeneration !== generation
      )
        return;

      const incomingData = response.data.indicator_data;
      if (!incomingData.length) {
        afterFetch.historyExhausted = true;
        return;
      }

      const previousEarliestTs = afterFetch.data[0]?.timestamp_ms ?? null;
      const mergedData = mergeIndicatorData(
        afterFetch.data,
        incomingData,
        latestRange,
      );
      context.updateIndicatorData(_id, mergedData);

      const updated = context.getById(_id);
      const nextEarliestTs = updated?.data[0]?.timestamp_ms ?? null;
      if (!updated || updated.historyGeneration !== generation) return;

      updated.hasExpandedHistory = true;
      updated.nextBackfillEndMs = nextEarliestTs;

      if (
        previousEarliestTs !== null &&
        nextEarliestTs !== null &&
        nextEarliestTs >= previousEarliestTs
      ) {
        updated.historyExhausted = true;
        return;
      }
    }
  } catch (error) {
    console.error('Failed to backfill indicator data', error);
  } finally {
    const indicator = context.getById(_id);
    if (indicator && indicator.historyGeneration === generation) {
      indicator.isBackfilling = false;
      indicator.activeBackfillPromise = null;
    }
  }
}
