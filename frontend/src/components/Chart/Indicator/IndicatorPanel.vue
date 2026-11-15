<template>
  <div class="indicator-panel">
    <div class="indicator-header">
      <span class="indicator-name"
        ><small v-if="indicator.ownerRunId">Backtest · </small
        >{{ indicator.info.name }}
        <small
          v-if="indicator.info.supports_live === false"
          title="Historical data only"
        >
          · Historical</small
        >
      </span>
      <div class="indicator-controls">
        <n-button
          text
          circle
          aria-label="Indicator settings"
          @click="onOpenSettings"
        >
          <n-icon size="20">
            <SettingsOutline />
          </n-icon>
        </n-button>
        <n-button
          text
          circle
          aria-label="Remove Indicator"
          v-if="!indicator.ownerRunId"
          class="remove-button"
          @click="onRemoveIndicator"
        >
          <n-icon size="20">
            <TrashOutline />
          </n-icon>
        </n-button>
        <BasePopover
          v-if="hasNoData"
          v-model:show="showEmptyState"
          trigger="hover"
          :width="260"
        >
          <template #trigger>
            <n-button
              text
              circle
              class="indicator-empty-state"
              aria-label="No data available for this symbol and indicator."
              @focus="showEmptyState = true"
              @blur="showEmptyState = false"
              @click="showEmptyState = true"
              @keydown.esc="showEmptyState = false"
            >
              <n-icon
                size="20"
                color="var(--design-color-error)"
              >
                <AlertCircleOutline />
              </n-icon>
            </n-button>
          </template>
          No data available for this symbol and indicator.
        </BasePopover>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { NButton, NIcon } from 'naive-ui';

import AlertCircleOutline from '@vicons/ionicons5/es/AlertCircleOutline';
import SettingsOutline from '@vicons/ionicons5/es/SettingsOutline';
import TrashOutline from '@vicons/ionicons5/es/TrashOutline';
import BasePopover from '@/components/Common/BasePopover.vue';
import { useModalStore } from '@/stores/modalStore';

import type { IndicatorInstance } from './types';
import type { IndicatorDataPoint } from '@/types/contracts';

defineOptions({
  name: 'IndicatorPanel',
});

const props = defineProps<{
  indicator: IndicatorInstance;
}>();

const emit = defineEmits<{
  'remove-indicator': [indicatorId: string];
}>();

const modalStore = useModalStore();
const showEmptyState = ref(false);

const hasNoData = computed(() => {
  if (props.indicator.info.indicator_id !== 'currency_strength') return false;
  if (props.indicator.info.overlay) return false;
  const outputs = Object.keys(props.indicator.info.outputs).filter(
    (key) => key !== 'timestamp',
  );
  const hasValue = (point: IndicatorDataPoint) =>
    Number.isFinite(point.timestamp_ms) &&
    outputs.some(
      (key) => typeof point[key] === 'number' && Number.isFinite(point[key]),
    );
  return !(
    (props.indicator.lastLivePoint &&
      hasValue(props.indicator.lastLivePoint)) ||
    props.indicator.data.some(hasValue)
  );
});

watch(hasNoData, () => {
  showEmptyState.value = false;
});

function onOpenSettings(): void {
  modalStore.openModal(`indicatorSettings_${props.indicator._id}`);
}

function onRemoveIndicator(): void {
  emit('remove-indicator', props.indicator._id);
}
</script>

<style scoped>
.indicator-name {
  min-width: 0;
  font-size: var(--design-text-body);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.indicator-panel {
  box-sizing: border-box;
  width: max-content;
  max-width: 100%;
  background: var(--design-color-panel);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  padding: var(--design-space-sm) var(--design-space-md);
  margin-bottom: var(--design-space-sm);
}

.indicator-header {
  display: flex;
  align-items: center;
  gap: var(--design-space-md);
}

.indicator-controls {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: var(--design-space-xs);
}

.indicator-empty-state {
  cursor: help;
}

.remove-button:hover {
  color: var(--design-color-error);
}
</style>
