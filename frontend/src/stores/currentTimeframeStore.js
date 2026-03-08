import { getStoredState, setStoredState, STORAGE_KEYS } from '@/utils/localStorage';
import { normalizeTimeframeCode } from '@/utils/timeframes';
import { defineStore } from 'pinia';

export const useCurrentTimeframeStore = defineStore('currentTimeframe', {
  state: () => {
    const stored = getStoredState(STORAGE_KEYS.CURRENT_TIMEFRAME);
    const value = normalizeTimeframeCode(stored?.value ?? 'M1');

    return {
      label: value,
      value,
    };
  },

  actions: {
    setCurrentTimeframe(timeframe) {
      this.label = timeframe.label;
      this.value = timeframe.value;

      setStoredState(STORAGE_KEYS.CURRENT_TIMEFRAME, {
        label: this.label,
        value: this.value,
      });
    },
  },
});
