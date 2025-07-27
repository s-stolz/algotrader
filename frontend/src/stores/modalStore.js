import { defineStore } from 'pinia';

export const useModalStore = defineStore('modal', {
  state: () => ({
    activeModal: null,
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
    },
  },
});
