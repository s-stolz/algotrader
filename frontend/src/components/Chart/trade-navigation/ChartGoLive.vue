<template>
  <span
    v-if="loading"
    class="history-loading"
    role="status"
    >Loading history…</span
  >
  <n-button
    class="chart-go-live"
    circle
    title="Go to latest candle"
    aria-label="Go to latest candle"
    :disabled="!ready"
    @click="$emit('activate')"
  >
    <n-icon size="20"><PlaySkipForwardOutline /></n-icon>
  </n-button>
</template>
<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';
import { PlaySkipForwardOutline } from '@/icons';
defineProps<{ ready: boolean; loading: boolean }>();
defineEmits<{ activate: [] }>();
</script>
<style scoped>
.history-loading {
  position: absolute;
  right: var(--design-space-md);
  top: var(--design-space-sm);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
  pointer-events: none;
}

.chart-go-live {
  position: absolute;
  right: 80px;
  bottom: 40px;
  z-index: 2;
  background: var(--design-color-panel);
}
</style>
