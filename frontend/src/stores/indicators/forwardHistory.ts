import { requestIndicator } from '@/api/indicatorClient';
import type { ChartRecoveryQuery } from '@/types/chartRecovery';
import type { ChartCandle, IndicatorDataPoint } from '@/types/contracts';
import { extractParameterValues } from './configuration';
import { mergeIndicatorData } from './historyData';
import { waitForIndicatorRequest } from './pendingRequests';
import type { StoreIndicator } from './types';
import { timeframeToMinutes } from '@/utils/timeframes';

interface ForwardHistoryStore {
  all: StoreIndicator[];
  getById(id: string): StoreIndicator | undefined;
  updateIndicatorData(id: string, data: IndicatorDataPoint[]): void;
}

export async function extendIndicatorHistory(
  store: ForwardHistoryStore,
  key: Omit<ChartRecoveryQuery, 'startMs' | 'endMs'>,
  candles: readonly ChartCandle[],
  signal: AbortSignal,
): Promise<void> {
  const first = candles[0];
  const last = candles.at(-1);
  if (!first || !last) return;
  await Promise.all(
    store.all.map(async (indicator) => {
      await waitForIndicatorRequest(indicator);
      signal.throwIfAborted();
      const generation = indicator.historyGeneration;
      const response = await requestIndicator(
        indicator.indicatorId,
        {
          ...key,
          startMs: first.timestamp_ms,
          endMs: last.timestamp_ms + timeframeToMinutes(key.timeframe) * 60_000,
        },
        { parameters: extractParameterValues(indicator.parameters) },
        signal,
      );
      if (
        signal.aborted ||
        store.getById(indicator._id) !== indicator ||
        indicator.historyGeneration !== generation
      )
        return;
      store.updateIndicatorData(
        indicator._id,
        mergeIndicatorData(indicator.data, response.data.indicator_data, null),
      );
    }),
  );
}
