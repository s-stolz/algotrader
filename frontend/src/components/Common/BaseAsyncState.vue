<script setup lang="ts">
import { NButton, NIcon, NSpin } from 'naive-ui';
import {
  AlertCircleOutline,
  FileTrayOutline,
  RefreshOutline,
  InformationCircleOutline,
} from '@vicons/ionicons5';
withDefaults(
  defineProps<{
    kind: 'loading' | 'error' | 'empty' | 'info';
    label: string;
    message?: string;
    compact?: boolean;
    retry?: boolean;
    retrying?: boolean;
  }>(),
  { message: '', compact: false, retry: false, retrying: false },
);
defineEmits<{ retry: [] }>();
</script>
<template>
  <div
    class="state-feedback"
    :class="[kind, { compact }]"
    :role="kind === 'error' ? 'alert' : 'status'"
    :aria-label="label"
    :aria-busy="kind === 'loading'"
  >
    <div
      class="state-symbol"
      aria-hidden="true"
    >
      <NSpin
        v-if="kind === 'loading'"
        :size="28"
      />
      <NIcon
        v-else
        :size="30"
        :component="
          kind === 'error'
            ? AlertCircleOutline
            : kind === 'info'
              ? InformationCircleOutline
              : FileTrayOutline
        "
      />
    </div>
    <div class="state-copy"
      ><p v-if="kind !== 'loading' && message">{{ message }}</p></div
    >
    <div class="state-action">
      <NButton
        v-if="retry && kind !== 'loading'"
        :loading="retrying"
        :disabled="retrying"
        circle
        quaternary
        size="small"
        :aria-label="`Retry: ${label}`"
        :title="`Retry: ${label}`"
        @click="$emit('retry')"
      >
        <template #icon><NIcon :component="RefreshOutline" /></template>
      </NButton>
    </div>
  </div>
</template>
<style scoped>
.state-feedback {
  box-sizing: border-box;
  min-height: 260px;
  display: grid;
  grid-template-rows: 40px minmax(44px, auto) 32px;
  align-content: center;
  justify-items: center;
  padding: 24px;
  color: var(--design-color-muted);
  text-align: center;
}
.state-feedback.compact {
  min-height: 160px;
  padding: 12px;
}
.state-symbol {
  display: grid;
  place-items: center;
}
.error .state-symbol {
  color: var(--design-color-error);
}
.state-copy {
  display: grid;
  align-items: center;
  max-width: 360px;
}
.state-copy p {
  margin: 0;
  font-size: var(--design-text-secondary);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.state-action {
  display: grid;
  place-items: center;
}
@media (prefers-reduced-motion: reduce) {
  :deep(.n-base-loading .n-base-loading__icon) {
    animation-duration: 4s;
  }
}
</style>
