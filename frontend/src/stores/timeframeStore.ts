import { defineStore } from 'pinia';
import { ref } from 'vue';

import type { TimeframeCode } from '@/types/contracts';

interface LegacyTimeframeOption {
  name: TimeframeCode;
  value: TimeframeCode;
}

export const useTimeframeStore = defineStore('timeframe', () => {
  const currentTimeframe = ref<LegacyTimeframeOption>({ name: 'M1', value: 'M1' });

  function setCurrentTimeframe(timeframe: LegacyTimeframeOption): void {
    currentTimeframe.value = timeframe;
  }

  function getCurrentTimeframe(): LegacyTimeframeOption {
    return currentTimeframe.value;
  }

  return {
    currentTimeframe,
    setCurrentTimeframe,
    getCurrentTimeframe,
  };
});
