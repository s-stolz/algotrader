import { waitForIndicatorRequest } from './pendingRequests';
import type { ChartRecoveryQuery } from '@/types/chartRecovery';
import { requestIndicator } from '@/api/indicatorClient';
import type {
  IndicatorDataPoint,
  IndicatorUpdateMessage,
} from '@/types/contracts';
import { wsService } from '@/utils/websocketService';
import { extractParameterValues } from './configuration';
import { mergeIndicatorData, mergeLivePoint } from './historyData';
import type { StoreIndicator } from './types';

interface RecoveryStore {
  all: StoreIndicator[];
  getById(id: string): StoreIndicator | undefined;
  updateIndicatorData(id: string, data: IndicatorDataPoint[]): void;
}

export async function recoverIndicatorHistory(
  store: RecoveryStore,
  query: ChartRecoveryQuery,
  isCurrent: () => boolean,
  signal: AbortSignal,
): Promise<void> {
  const targets = store.all.map((indicator) => ({
    indicator,
    generation: indicator.historyGeneration,
    parameters: extractParameterValues(indicator.parameters),
    live: new Map<number, IndicatorDataPoint>(),
  }));
  const onLive = (message: IndicatorUpdateMessage) => {
    if (!isCurrent()) return;
    const target = targets.find(
      (item) => item.indicator._id === message.clientIndicatorId,
    );
    if (!target) return;
    const point = mergeLivePoint(
      target.live.get(message.timestamp_ms) ?? null,
      message,
    );
    if (point) target.live.set(point.timestamp_ms, point);
  };
  const cleanup = () => wsService.off('indicatorUpdate', onLive);
  wsService.on('indicatorUpdate', onLive);
  signal.addEventListener('abort', cleanup, { once: true });
  try {
    const results = await Promise.allSettled(
      targets.map(async (target) => {
        const { indicator, generation, parameters, live } = target;
        await waitForIndicatorRequest(indicator);
        if (
          !isCurrent() ||
          store.getById(indicator._id) !== indicator ||
          indicator.historyGeneration !== generation
        )
          return;
        const response = await requestIndicator(indicator.indicatorId, query, {
          parameters,
        });
        if (
          !isCurrent() ||
          store.getById(indicator._id) !== indicator ||
          indicator.historyGeneration !== generation ||
          JSON.stringify(extractParameterValues(indicator.parameters)) !==
            JSON.stringify(parameters)
        )
          return;
        // Recovery corrects old duplicates; samples received during this request win.
        const recovered = mergeIndicatorData(
          response.data.indicator_data,
          indicator.data,
          null,
        );
        const merged = new Map(
          recovered.map((point) => [point.timestamp_ms, point]),
        );
        for (const point of live.values()) {
          merged.set(point.timestamp_ms, {
            ...merged.get(point.timestamp_ms),
            ...point,
          });
        }
        store.updateIndicatorData(
          indicator._id,
          [...merged.values()].sort(
            (left, right) => left.timestamp_ms - right.timestamp_ms,
          ),
        );
      }),
    );
    const failed = results.find((result) => result.status === 'rejected');
    if (failed?.status === 'rejected') throw failed.reason;
  } finally {
    cleanup();
    signal.removeEventListener('abort', cleanup);
  }
}
