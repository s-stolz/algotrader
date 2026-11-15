<script setup lang="ts">
import { ref, watch } from 'vue';
import { designCssProperties } from '@/design/cssProperties';
import { NModal, NScrollbar, NStep, NSteps } from 'naive-ui';

const props = defineProps<{
  show: boolean;
  title: string;
  steps: string[];
  step: number;
  fillBody?: boolean;
}>();
const emit = defineEmits<{
  'update:show': [show: boolean];
  'update:step': [step: number];
}>();
const scrollbar = ref<InstanceType<typeof NScrollbar>>();
watch(
  () => props.step,
  () => scrollbar.value?.scrollTo({ top: 0 }),
);
</script>
<template>
  <n-modal
    :show="show"
    :style="designCssProperties"
    :mask-closable="false"
    :auto-focus="true"
    preset="card"
    :content-style="{
      display: 'flex',
      flexDirection: 'column',
      minHeight: '0px',
      overflow: 'hidden',
    }"
    :title="title"
    class="base-step-modal"
    @update:show="emit('update:show', $event)"
  >
    <nav
      class="steps-navigation"
      aria-label="Creation steps"
    >
      <n-steps
        :current="step + 1"
        size="small"
        @update:current="emit('update:step', $event - 1)"
      >
        <n-step
          v-for="(name, index) in steps"
          :key="name"
        >
          <template #title
            ><button
              class="step-button"
              :aria-current="step === index ? 'step' : undefined"
              @click="emit('update:step', index)"
              >{{ name }}</button
            ></template
          >
        </n-step>
      </n-steps>
    </nav>
    <n-scrollbar
      ref="scrollbar"
      class="step-body"
      :content-style="{
        paddingRight: '22px',
        boxSizing: 'border-box',
        height: fillBody ? '100%' : undefined,
      }"
    >
      <slot />
    </n-scrollbar>
    <template #footer><slot name="footer" /></template>
  </n-modal>
</template>
<style scoped>
/* Keep the indicators' outer box-shadow borders inside the clipped card content. */
.steps-navigation {
  width: 100%;
  padding-top: 2px;
  padding-bottom: 20px;
  flex-shrink: 0;
}
.steps-navigation :deep(.n-step:last-child) {
  flex: 0 0 auto;
}
.step-button {
  border: 0;
  padding: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.step-button:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: 4px;
}
</style>
<style>
.base-step-modal.n-card {
  width: min(700px, calc(100vw - 32px));
  height: min(800px, calc(100dvh - 110px));
  margin: 24px auto 90px;
  background: var(--design-color-panel);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  font-family: var(--design-font-ui);
  font-size: var(--design-text-body);
}
.base-step-modal .step-body {
  flex: 1;
  min-height: 0;
  max-height: none;
  overflow: hidden;
}
.base-step-modal.n-card > .n-card__footer {
  flex-shrink: 0;
}
</style>
