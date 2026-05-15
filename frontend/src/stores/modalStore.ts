import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useModalStore = defineStore('modal', () => {
  const activeModal = ref<string | null>(null);

  function openModal(name: string): void {
    activeModal.value = name;
  }

  function closeModal(): void {
    activeModal.value = null;
  }

  function isModalOpen(name: string): boolean {
    return activeModal.value === name;
  }

  return {
    activeModal,
    openModal,
    closeModal,
    isModalOpen,
  };
});
