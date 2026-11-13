<script setup lang="ts">
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';
withDefaults(defineProps<{ overlay?: boolean }>(), { overlay: false });
</script>
<template>
  <div
    class="replay-loading"
    :class="{ overlay }"
  >
    <BaseAsyncState
      kind="loading"
      label="Loading equity replay"
    />
  </div>
</template>
<style scoped>
.overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: grid;
  place-items: center;
  pointer-events: none;
  background: color-mix(in srgb, var(--design-color-panel) 65%, transparent);
}
</style>
