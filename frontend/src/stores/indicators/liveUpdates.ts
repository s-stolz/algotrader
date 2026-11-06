import { markRaw } from 'vue';
import type { IndicatorUpdateMessage } from '@/types/contracts';
import type { IndicatorCoverageOptions, StoreIndicator } from './types';
import { getLoadedCandleRange } from './historyCoverage';
import {
  mergeIndicatorData,
  mergeLivePoint,
  retainLivePoint,
  trimDataToRange,
} from './historyData';

export function applyIndicatorUpdate(
  indicator: StoreIndicator,
  message: IndicatorUpdateMessage,
  coverage: IndicatorCoverageOptions | null,
) {
  if (!message.replay) {
    const point = mergeLivePoint(indicator.lastLivePoint, message);
    return retainLivePoint(indicator, point);
  }

  const point = mergeLivePoint(null, message);
  if (!point) return null;
  const range = getLoadedCandleRange(coverage ?? {});
  if (!trimDataToRange([point], range).length) return null;
  indicator.data = markRaw(mergeIndicatorData([point], indicator.data, null));
  indicator.currentLimit = indicator.data.length;
  indicator.lastLivePoint = indicator.data.at(-1) ?? null;
  indicator.dataVersion += 1;
  return null;
}
