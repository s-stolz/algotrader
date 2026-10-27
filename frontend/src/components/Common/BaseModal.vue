<template>
  <div
    v-if="isModalOpen"
    class="modal-backdrop"
    :class="{ 'modal-backdrop--design': usesDesign }"
    @mousedown="onMouseDown"
    @mouseup="onMouseUp"
  >
    <div
      class="modal"
      @click.stop
    >
      <header class="modal-header">
        <div class="header-content">
          <h2 class="title">{{ title }}</h2>
          <n-button
            text
            :circle="usesDesign"
            aria-label="Close dialog"
            class="close-button"
            @click="close"
          >
            <n-icon size="24">
              <CloseCircleOutline />
            </n-icon>
          </n-button>
        </div>
        <hr class="separator" />
      </header>
      <div class="modal-body">
        <slot></slot>
      </div>
      <template v-if="$slots.footer">
        <hr class="separator" />
        <footer class="modal-footer">
          <slot name="footer"></slot>
        </footer>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { NButton, NIcon } from 'naive-ui';

import { CloseCircleOutline } from '@/icons';
import { useDesignScope } from '@/design/scope';
import { useModalStore } from '@/stores/modalStore';

defineOptions({
  name: 'BaseModal',
});

const props = withDefaults(
  defineProps<{
    closeOnBackdrop?: boolean;
    modalId: string;
    title?: string;
  }>(),
  {
    closeOnBackdrop: true,
    title: 'Modal Title',
  },
);

const usesDesign = useDesignScope();
const modalStore = useModalStore();
const isMouseDownInside = ref(false);
const isModalOpen = computed(() => modalStore.isModalOpen(props.modalId));

function close(): void {
  modalStore.closeModal();
}

function onMouseDown(event: MouseEvent): void {
  const target = event.target instanceof Element ? event.target : null;
  isMouseDownInside.value = target?.closest('.modal') !== null;
}

function onMouseUp(): void {
  if (!isMouseDownInside.value && props.closeOnBackdrop) {
    close();
  }
}

defineExpose({ close });
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.modal {
  position: relative;
  background: var(--surface-panel);
  border-radius: 15px;
  border: 1px solid var(--surface-border);
  max-width: 550px;
  width: 100%;
  padding: 0;
  overflow: hidden;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.modal-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header .title {
  margin: 0;
  padding-top: 10px;
  padding-left: 15px;
}

.modal .separator {
  border: none;
  height: 1px;
  background-color: var(--surface-border);
  margin: 0;
}

.modal :deep(.separator) {
  background-color: var(--surface-border);
}

.modal-footer {
  padding: 10px 15px;
  text-align: right;
}

.modal-body {
  overflow-y: auto;
  box-sizing: border-box;
}

.close-button {
  position: absolute;
  top: 10px;
  right: 10px;
}

.close-button:hover {
  color: #e98b8b;
}

.modal-backdrop--design {
  background: var(--design-color-backdrop);
  box-sizing: border-box;
  padding: var(--design-space-sm);
  font-family: var(--design-font-ui);
  font-size: var(--design-text-body);
  color: var(--design-color-body);
}

.modal-backdrop--design .modal {
  display: flex;
  flex-direction: column;
  max-height: 100%;
  background: var(--design-color-panel);
  border-color: var(--design-color-border);
  border-radius: var(--design-radius-panel);
  box-shadow: var(--design-shadow-overlay);
}

.modal-backdrop--design .modal-header,
.modal-backdrop--design .modal-footer {
  flex-shrink: 0;
}

.modal-backdrop--design .modal-header {
  gap: var(--design-space-sm);
}

.modal-backdrop--design .title {
  padding: var(--design-space-md) var(--design-space-lg);
  padding-right: calc(var(--design-control-medium) + var(--design-space-lg));
  font-size: var(--design-text-heading);
}

.modal-backdrop--design .modal-footer {
  padding: var(--design-space-md) var(--design-space-lg);
}

.modal-backdrop--design .separator {
  background: var(--design-color-border);
}

.modal-backdrop--design .close-button {
  top: var(--design-space-sm);
  right: var(--design-space-sm);
}

.modal-backdrop--design .close-button:hover {
  color: var(--design-color-error);
}
</style>
