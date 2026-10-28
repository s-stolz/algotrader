<template>
  <div class="indicator-panel">
    <div class="indicator-header">
      <span class="indicator-name">{{ indicator.info.name }}</span>
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
          class="remove-button"
          @click="onRemoveIndicator"
        >
          <n-icon size="20">
            <TrashOutline />
          </n-icon>
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';

import { SettingsOutline, TrashOutline } from '@/icons';
import { useModalStore } from '@/stores/modalStore';

import type { IndicatorInstance } from './types';

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

function onOpenSettings(): void {
  modalStore.openModal(`indicatorSettings_${props.indicator._id}`);
}

function onRemoveIndicator(): void {
  emit('remove-indicator', props.indicator._id);
}
</script>

<style scoped>
.indicator-name {
  font-size: var(--design-text-body);
  white-space: nowrap;
  overflow: ellipsis;
}

.indicator-panel {
  background: var(--design-color-panel);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  padding: var(--design-space-sm) var(--design-space-md);
  margin-bottom: var(--design-space-sm);
  min-width: 300px;
}

.indicator-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.indicator-controls {
  display: flex;
  align-items: center;
  gap: var(--design-space-xs);
}

.remove-button:hover {
  color: var(--design-color-error);
}
</style>
