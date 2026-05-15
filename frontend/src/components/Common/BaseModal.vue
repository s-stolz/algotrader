<template>
  <div
    v-if="isModalOpen"
    class="modal-backdrop"
    @mousedown="onMouseDown"
    @mouseup="onMouseUp"
  >
    <div class="modal" @click.stop>
      <header class="modal-header">
        <div class="header-content">
          <h2 class="title">{{ title }}</h2>
          <n-button text class="close-button" @click="close">
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
      </template>
      <footer class="modal-footer">
        <slot name="footer"></slot>
      </footer>
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

const props = withDefaults(defineProps<{
  closeOnBackdrop?: boolean;
  modalId: string;
  title?: string;
}>(), {
  closeOnBackdrop: true,
  title: 'Modal Title',
});

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
  background: #131722;
  border-radius: 15px;
  border: 3px solid rgb(13, 14, 16);
  max-width: 550px;
  width: 100%;
  padding: 0;
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
  background-color: #ddd;
  margin: 0;
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
</style>
