<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import AlertCircleOutline from '@vicons/ionicons5/es/AlertCircleOutline';
import InformationCircleOutline from '@vicons/ionicons5/es/InformationCircleOutline';
import BasePopover from '@/components/Common/BasePopover.vue';
defineProps<{ label: string; error?: boolean }>();
const show = ref(false);
</script>
<template>
  <BasePopover
    v-model:show="show"
    trigger="hover"
    :width="360"
  >
    <template #trigger>
      <n-button
        text
        :aria-label="error ? `Error: ${label}` : `About ${label}`"
        :type="error ? 'error' : 'default'"
        @focus="show = true"
        @blur="show = false"
        @click="show = true"
        @keydown.esc="show = false"
      >
        <n-icon
          :component="error ? AlertCircleOutline : InformationCircleOutline"
          :size="17"
        />
      </n-button>
    </template>
    <div class="help"><slot /></div>
  </BasePopover>
</template>
<style scoped>
.help :deep(p) {
  margin: 0 0 10px;
  line-height: 1.5;
}
.help :deep(p:last-child) {
  margin-bottom: 0;
}
</style>
