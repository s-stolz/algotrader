import { defineStore } from 'pinia';
import { ref } from 'vue';

import {
  isRecord,
  isStoredCurrentTimeframe,
  type TimeframeCode,
  type TimeframeOption,
} from '@/types/contracts';
import { getStoredState, setStoredState, STORAGE_KEYS } from '@/utils/localStorage';
import { normalizeTimeframeCode } from '@/utils/timeframes';

function readStoredTimeframe(): TimeframeCode {
  const stored = getStoredState<unknown>(STORAGE_KEYS.CURRENT_TIMEFRAME);

  if (isStoredCurrentTimeframe(stored)) {
    return stored.value;
  }

  if (isRecord(stored)) {
    return normalizeTimeframeCode(stored.value);
  }

  return 'M1';
}

export const useCurrentTimeframeStore = defineStore('currentTimeframe', () => {
  const initial = readStoredTimeframe();
  const label = ref<TimeframeCode>(initial);
  const value = ref<TimeframeCode>(initial);

  function setCurrentTimeframe(timeframe: TimeframeOption): void {
    const normalized = normalizeTimeframeCode(timeframe.value);

    label.value = normalized;
    value.value = normalized;

    setStoredState(STORAGE_KEYS.CURRENT_TIMEFRAME, {
      label: label.value,
      value: value.value,
    });
  }

  return {
    label,
    value,
    setCurrentTimeframe,
  };
});
