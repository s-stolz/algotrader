<template>
  <div>
    <symbol-search-modal
      ref="symbolSearchModal"
      v-show="modalStore.isModalOpen('symbolSearch')"
      @openSymbolFormModal="onOpenSymbolFormModal"
      @removeMarket="onRemoveMarket"
      @uploadData="onUploadData"
    />
    <indicator-search-modal v-if="modalStore.isModalOpen('indicatorSearch')" />
    <symbol-form-modal v-if="modalStore.isModalOpen('symbolForm')" />
    <remove-market-modal
      v-if="modalStore.isModalOpen('removeMarket')"
      :market="marketToRemove"
      @market-removed="onMarketRemoved"
    />
    <upload-data-modal
      v-if="modalStore.isModalOpen('uploadData')"
      :market="marketToUpload"
      @upload-successful="onUploadSuccessful"
    />
  </div>
</template>

<script>
import { useModalStore } from "@/stores/modalStore";

import SymbolSearchModal from "@/components/TopBar/Modals/SymbolSearchModal.vue";
import IndicatorSearchModal from "@/components/TopBar/Modals/IndicatorSearchModal.vue";
import SymbolFormModal from "@/components/TopBar/Modals/SymbolFormModal.vue";
import RemoveMarketModal from "@/components/TopBar/Modals/RemoveMarketModal.vue";
import UploadDataModal from "@/components/TopBar/Modals/Upload/UploadDataModal.vue";

export default {
  name: "TopBarModals",
  components: {
    SymbolSearchModal,
    IndicatorSearchModal,
    SymbolFormModal,
    RemoveMarketModal,
    UploadDataModal,
  },

  data() {
    return {
      modalStore: useModalStore(),
      marketToRemove: null,
      marketToUpload: null,
    };
  },

  methods: {
    onOpenSymbolFormModal() {
      this.modalStore.openModal("symbolForm");
    },

    onRemoveMarket(market) {
      this.marketToRemove = market;
      this.modalStore.openModal("removeMarket");
    },

    onUploadData(market) {
      this.marketToUpload = market;
      this.modalStore.openModal("uploadData");
    },

    onUploadSuccessful() {
      this.$refs.symbolSearchModal.updateCurrentMarket(this.marketToUpload);
      this.marketToUpload = null;
    },

    onMarketRemoved() {
      this.$refs.symbolSearchModal.updateCurrentMarket(this.marketToRemove);
      this.marketToRemove = null;
    },
  },
};
</script>
