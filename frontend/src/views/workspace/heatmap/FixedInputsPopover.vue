<template>
  <BasePopover
    v-model:show="open"
    trigger="click"
    placement="bottom-end"
    :show-arrow="false"
  >
    <template #trigger
      ><n-button
        ref="trigger"
        :aria-expanded="open"
        :aria-controls="open ? dialogId : undefined"
        @keydown.esc.stop="close"
        aria-haspopup="dialog"
      >
        <template #icon><n-icon :component="OptionsOutline" /></template>Fixed
        inputs
      </n-button></template
    >
    <div
      ref="dialog"
      :id="dialogId"
      tabindex="-1"
      class="fixed-popover"
      role="dialog"
      aria-label="Fixed inputs"
      @keydown.esc.stop="close"
    >
      <div class="popover-heading"
        ><strong>Fixed inputs</strong>
        <n-button
          quaternary
          circle
          aria-label="Close fixed inputs"
          @click="close"
        >
          <template #icon><n-icon :component="CloseOutline" /></template>
        </n-button>
      </div>
      <p v-if="!fields.length">No other varying inputs.</p>
      <div class="popover-fields"
        ><label
          v-for="field in fields"
          :key="field.key"
        >
          {{ field.label
          }}<BaseSelect
            :value="values[field.key]"
            :to="false"
            :aria-label="field.label"
            :options="field.options"
            @update:value="(value: string) => emit('change', field.key, value)"
          /> </label
      ></div>
    </div>
  </BasePopover>
</template>
<script setup lang="ts">
import { nextTick, ref, useId, watch } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import OptionsOutline from '@vicons/ionicons5/es/OptionsOutline';
import CloseOutline from '@vicons/ionicons5/es/CloseOutline';
import BasePopover from '@/components/Common/BasePopover.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import type { HeatmapDimension } from '@/types/backtest/heatmapSnapshot';
defineProps<{ fields: HeatmapDimension[]; values: Record<string, string> }>();
const emit = defineEmits<{ change: [key: string, value: string] }>();
const open = ref(false);
const dialogId = useId();
const dialog = ref<HTMLElement | null>(null);
const trigger = ref<{ $el: HTMLButtonElement } | null>(null);
watch(open, async (shown) => {
  if (!shown) return;
  await nextTick();
  if (open.value) dialog.value?.focus();
});
function close() {
  open.value = false;
  trigger.value?.$el.focus();
}
</script>
<style scoped>
.fixed-popover {
  width: min(540px, calc(100vw - 64px));
  padding: var(--design-space-sm);
}
.popover-heading {
  display: flex;
  align-items: center;
  gap: var(--design-space-lg);
  margin-bottom: var(--design-space-xl);
}
.popover-heading strong {
  margin-right: auto;
  font-size: var(--design-text-body);
}
.popover-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--design-space-xl) var(--design-space-lg);
}
label {
  display: flex;
  flex-direction: column;
  gap: var(--design-space-sm);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
@media (max-width: 550px) {
  .popover-fields {
    grid-template-columns: 1fr;
  }
}
</style>
