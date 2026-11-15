import { requestIndicator } from '@/api/indicatorClient';
import type { ChartRecoveryQuery } from '@/types/chartRecovery';
import type {
  ChartCandle,
  IndicatorUpdateMessage,
  IndicatorDataPoint,
} from '@/types/contracts';
import { extractParameterValues } from './configuration';
import { mergeIndicatorData, mergeLivePoint } from './historyData';
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

export function createIndicatorLiveBuffer() {
  let active = false;
  let accepting = false;
  const points = new Map<string, Map<number, IndicatorDataPoint>>();
  return {
    get active() {
      return active;
    },
    begin() {
      active = true;
      accepting = true;
      points.clear();
    },
    discard(hold = false) {
      active = hold;
      accepting = false;
      points.clear();
    },
    receive(message: IndicatorUpdateMessage) {
      if (!active) return false;
      if (!accepting) return true;
      let series = points.get(message.clientIndicatorId);
      if (!series) {
        series = new Map();
        points.set(message.clientIndicatorId, series);
      }
      const point = mergeLivePoint(
        series.get(message.timestamp_ms) ?? null,
        message,
      );
      if (point) series.set(point.timestamp_ms, point);
      return true;
    },
    finish(store: ForwardHistoryStore) {
      active = false;
      for (const [id, series] of points) {
        const indicator = store.getById(id);
        if (indicator)
          store.updateIndicatorData(
            id,
            mergeIndicatorData([...series.values()], indicator.data, null),
          );
      }
      points.clear();
    },
  };
}
