import { defineStore } from 'pinia';

export const useModalStore = defineStore('modal', {
  state: () => ({
    activeModal: null // e.g. 'indicatorSearch' | 'symbolForm' | 'symbolSearch'
  }),
  actions: {
    openModal(name) {
      this.activeModal = name;
    },
    closeModal() {
      this.activeModal = null;
    },
    isModalOpen(name) {
      return this.activeModal === name;
    }
  }
});
