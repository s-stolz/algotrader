<template>
  <n-popselect
    :default-value="timeframes[0].value"
    scrollable
    style="width: 80px; height: 150px;"
    @update:value="onTimeframeChange"
    :options="timeframes"
  >
    <n-button
      round
      class="timeframe-button"
    >
      {{ currentTimeframeStore.label }}
    </n-button>
  </n-popselect>
</template>

<script setup lang="ts">
import { NButton, NPopselect, type SelectOption } from 'naive-ui';

import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { normalizeTimeframeCode, TIMEFRAME_OPTIONS } from '@/utils/timeframes';

defineOptions({
  name: 'TimeframeDropdown',
});

const currentTimeframeStore = useCurrentTimeframeStore();
const timeframes: SelectOption[] = TIMEFRAME_OPTIONS.map((timeframe) => ({
  label: timeframe.label,
  value: timeframe.value,
}));

function onTimeframeChange(_value: string | number, option: SelectOption | null): void {
  const timeframe = normalizeTimeframeCode(option?.value);
  currentTimeframeStore.setCurrentTimeframe({
    label: timeframe,
    value: timeframe,
  });
}
</script>

<style scoped>
.timeframe-button {
  width: 80px;
}
</style>
