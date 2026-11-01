<template>
  <BasePopover
    v-if="notes.length"
    trigger="hover"
    :show="open"
  >
    <template #trigger>
      <button
        type="button"
        class="change-info"
        :aria-label="`${name} changes: ${notes.join('; ')}`"
        @mouseenter="open = true"
        @mouseleave="open = false"
        @focus="open = true"
        @blur="open = false"
        @click.prevent="open = true"
        @keydown.esc="open = false"
        >ⓘ</button
      >
    </template>
    <div
      v-for="note in notes"
      :key="note"
      >{{ note }}</div
    >
  </BasePopover>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue';
import BasePopover from '@/components/Common/BasePopover.vue';
import { useCreation } from './creationContext';
const props = defineProps<{ name: string }>();
const { parameterChanges } = useCreation();
const open = ref(false);
const notes = computed(() =>
  parameterChanges.value
    .filter((item) => item.parameter === props.name)
    .map((item) =>
      item.saved === undefined
        ? item.change
        : `${item.change}: ${item.saved} → ${item.current}`,
    ),
);
</script>
<style scoped>
.change-info {
  margin-left: var(--design-space-sm);
  padding: 0 var(--design-space-xs);
  border: 0;
  background: transparent;
  color: var(--design-color-muted);
  font: inherit;
  cursor: help;
}
.change-info:hover,
.change-info:focus-visible {
  color: var(--design-color-interactive);
}
</style>
