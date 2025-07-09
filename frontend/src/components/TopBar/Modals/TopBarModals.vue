<template>
  <div>
    <symbol-search-modal v-if="modalStore.isModalOpen('symbolSearch')" @openSymbolFormModal="onOpenSymbolFormModal"/>
    <indicator-search-modal v-if="modalStore.isModalOpen('indicatorSearch')" />
    <symbol-form-modal v-if="modalStore.isModalOpen('symbolForm')" />
  </div>
</template>

<script>
import { useModalStore } from '@/stores/modalStore';

import SymbolSearchModal from '@/components/TopBar/Modals/SymbolSearchModal.vue';
import IndicatorSearchModal from '@/components/TopBar/Modals/IndicatorSearchModal.vue';
import SymbolFormModal from '@/components/TopBar/Modals/SymbolFormModal.vue';

export default {
  name: 'TopBarModals',
  components: {
    SymbolSearchModal,
    IndicatorSearchModal,
    SymbolFormModal,
  },
  
  data() {
    return {
      modalStore: useModalStore(),
    };
  },

  methods: {
    onOpenSymbolFormModal() {
      this.modalStore.openModal('symbolForm');
    },
  },
};
</script>
