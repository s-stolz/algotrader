<template>
  <div class="indicator-panel">
    <div class="indicator-header">
      <span class="indicator-name">{{ indicator.info.name }}</span>
      <div class="indicator-controls">
        <n-button text @click="onOpenSettings">
          <n-icon size="20">
            <SettingsOutline />
          </n-icon>
        </n-button>
        <n-button text class="remove-button" @click="onRemoveIndicator">
          <n-icon size="20">
            <TrashOutline />
          </n-icon>
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NButton, NIcon } from "naive-ui";

import { SettingsOutline, TrashOutline } from "@/icons";
import { useModalStore } from "@/stores/modalStore";

import type { IndicatorInstance } from "./types";

defineOptions({
  name: "IndicatorPanel",
});

const props = defineProps<{
  indicator: IndicatorInstance;
}>();

const emit = defineEmits<{
  "remove-indicator": [indicatorId: string];
}>();

const modalStore = useModalStore();

function onOpenSettings(): void {
  modalStore.openModal(`indicatorSettings_${props.indicator._id}`);
}

function onRemoveIndicator(): void {
  emit("remove-indicator", props.indicator._id);
}
</script>

<style scoped>
.indicator-name {
  font-size: 14px;
  white-space: nowrap;
  overflow: ellipsis;
}

.indicator-panel {
  background: rgba(19, 23, 34, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
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
  gap: 4px;
}

.remove-button:hover {
  color: #e98b8b;
}
</style>
