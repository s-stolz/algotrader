<template>
  <div
    v-if="loading"
    class="history-loading"
    role="status"
    aria-label="Loading history"
  >
    <n-spin :size="18" />
  </div>
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
import { NButton, NIcon, NSpin } from 'naive-ui';
import PlaySkipForwardOutline from '@vicons/ionicons5/es/PlaySkipForwardOutline';
defineProps<{ ready: boolean; loading: boolean }>();
defineEmits<{ activate: [] }>();
</script>
<style scoped>
.history-loading {
  position: absolute;
  right: var(--design-space-md);
  top: var(--design-space-sm);
  z-index: 2;
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
