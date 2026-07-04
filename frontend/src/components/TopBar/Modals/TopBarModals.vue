<template>
  <div>
    <SymbolSearchModal
      ref="symbolSearchModal"
      v-show="modalStore.isModalOpen('symbolSearch')"
      @open-symbol-form-modal="onOpenSymbolFormModal"
      @remove-market="onRemoveMarket"
      @upload-data="onUploadData"
    />
    <IndicatorSearchModal v-if="modalStore.isModalOpen('indicatorSearch')" />
    <BacktestRunHistoryModal v-if="modalStore.isModalOpen('backtestRuns')" />
    <SymbolFormModal v-if="modalStore.isModalOpen('symbolForm')" />
    <RemoveMarketModal
      v-if="modalStore.isModalOpen('removeMarket') && marketToRemove"
      :market="marketToRemove"
      @market-removed="onMarketRemoved"
    />
    <UploadDataModal
      v-if="modalStore.isModalOpen('uploadData') && marketToUpload"
      :market="marketToUpload"
      @upload-successful="onUploadSuccessful"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, type ComponentPublicInstance } from 'vue';

import BacktestRunHistoryModal from '@/components/TopBar/Modals/BacktestRunHistoryModal.vue';
import IndicatorSearchModal from '@/components/TopBar/Modals/IndicatorSearchModal.vue';
import RemoveMarketModal from '@/components/TopBar/Modals/RemoveMarketModal.vue';
import SymbolFormModal from '@/components/TopBar/Modals/SymbolFormModal.vue';
import SymbolSearchModal from '@/components/TopBar/Modals/SymbolSearchModal.vue';
import UploadDataModal from '@/components/TopBar/Modals/Upload/UploadDataModal.vue';
import { useModalStore } from '@/stores/modalStore';
import type { Market } from '@/types/contracts';

defineOptions({
  name: 'TopBarModals',
});

type SymbolSearchModalInstance = ComponentPublicInstance & {
  updateCurrentMarket: (market: Market) => void;
};

const modalStore = useModalStore();
const symbolSearchModal = ref<SymbolSearchModalInstance | null>(null);
const marketToRemove = ref<Market | null>(null);
const marketToUpload = ref<Market | null>(null);

function onOpenSymbolFormModal(): void {
  modalStore.openModal('symbolForm');
}

function onRemoveMarket(market: Market): void {
  marketToRemove.value = market;
  modalStore.openModal('removeMarket');
}

function onUploadData(market: Market): void {
  marketToUpload.value = market;
  modalStore.openModal('uploadData');
}

function onUploadSuccessful(): void {
  if (marketToUpload.value) {
    symbolSearchModal.value?.updateCurrentMarket(marketToUpload.value);
  }
  marketToUpload.value = null;
}

function onMarketRemoved(): void {
  if (marketToRemove.value) {
    symbolSearchModal.value?.updateCurrentMarket(marketToRemove.value);
  }
  marketToRemove.value = null;
}
</script>
