import { getStoredState, setStoredState, STORAGE_KEYS } from '@/utils/localStorage';
import { defineStore } from 'pinia';

export const useCurrentTimeframeStore = defineStore('currentTimeframe', {
  state: () => {
    const stored = getStoredState(STORAGE_KEYS.CURRENT_TIMEFRAME);

    return {
      label: stored?.label ?? '1M',
      value: stored?.value ?? 1,
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
