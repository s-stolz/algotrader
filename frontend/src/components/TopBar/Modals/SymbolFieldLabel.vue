<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import InformationCircleOutline from '@vicons/ionicons5/es/InformationCircleOutline';
import BasePopover from '@/components/Common/BasePopover.vue';

defineProps<{ label: string }>();
const show = ref(false);
</script>

<template>
  <div class="field-label">
    <span>{{ label }}</span>
    <BasePopover
      v-model:show="show"
      trigger="hover"
      placement="top"
      :width="280"
    >
      <template #trigger>
        <n-button
          text
          :aria-label="`About ${label}`"
          @focus="show = true"
          @blur="show = false"
          @click="show = true"
          @keydown.esc="show = false"
        >
          <n-icon
            :component="InformationCircleOutline"
            :size="17"
          />
        </n-button>
      </template>
      <div
        class="field-help"
        role="tooltip"
        ><slot
      /></div>
    </BasePopover>
  </div>
</template>

<style scoped>
.field-label {
  display: flex;
  align-items: center;
  gap: var(--design-space-xs);
  font-weight: 600;
}
.field-help {
  font-size: var(--design-text-secondary);
  line-height: 1.5;
}
</style>
