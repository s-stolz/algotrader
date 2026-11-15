<template>
  <div
    v-if="isModalOpen"
    class="modal-backdrop"
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
            circle
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
  background: var(--design-color-backdrop);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  box-sizing: border-box;
  padding: var(--design-space-sm);
  font-family: var(--design-font-ui);
  font-size: var(--design-text-body);
  color: var(--design-color-body);
}
.modal {
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--design-color-panel);
  border-radius: var(--design-radius-panel);
  border: 1px solid var(--design-color-border);
  max-width: 550px;
  max-height: 100%;
  width: 100%;
  padding: 0;
  overflow: hidden;
  box-shadow: var(--design-shadow-overlay);
}
.modal-header {
  display: flex;
  flex-direction: column;
  gap: var(--design-space-sm);
}
.modal-header,
.modal-footer {
  flex-shrink: 0;
}
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  margin: 0;
  padding: var(--design-space-md) var(--design-space-lg);
  padding-right: calc(var(--design-control-medium) + var(--design-space-lg));
  font-size: var(--design-text-heading);
}
.modal .separator {
  border: none;
  height: 1px;
  background-color: var(--design-color-border);
  margin: 0;
}
.modal :deep(.separator) {
  background-color: var(--design-color-border);
}
.modal-footer {
  padding: var(--design-space-md) var(--design-space-lg);
  text-align: right;
}
.modal-body {
  overflow-y: auto;
  box-sizing: border-box;
}
.close-button {
  position: absolute;
  top: var(--design-space-sm);
  right: var(--design-space-sm);
}
.close-button:hover {
  color: var(--design-color-error);
}
</style>
