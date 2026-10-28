<script setup lang="ts">
import BaseGroupedSelect from '@/components/Common/BaseGroupedSelect.vue';
import { useCurrentTimeframeStore } from '@/stores/currentTimeframeStore';
import { groupTimeframeOptions, TIMEFRAME_OPTIONS } from '@/utils/timeframes';
import { isTimeframeCode } from '@/types/contracts';

const currentTimeframeStore = useCurrentTimeframeStore();
const groups = groupTimeframeOptions(TIMEFRAME_OPTIONS);

function selectTimeframe(value: string): void {
  if (isTimeframeCode(value)) {
    currentTimeframeStore.setCurrentTimeframe({ label: value, value });
  }
}
</script>

<template>
  <BaseGroupedSelect
    :value="currentTimeframeStore.value"
    label="Timeframe"
    :groups="groups"
    trigger-width="80px"
    @update:value="selectTimeframe"
  />
</template>
