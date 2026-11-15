<template>
  <div>
    <SymbolSearchModal
      v-if="hasOpenedSymbolSearch"
      v-show="modalStore.isModalOpen('symbolSearch')"
      @open-symbol-form-modal="onOpenSymbolFormModal"
      @remove-market="onRemoveMarket"
      @upload-data="onUploadData"
      @edit-market="onEditMarket"
      @download-history="onDownloadHistory"
    />
    <IndicatorSearchModal v-if="modalStore.isModalOpen('indicatorSearch')" />
    <SymbolFormModal
      v-if="modalStore.isModalOpen('symbolForm')"
      :market="marketToEdit"
      @created="onMarketCreated"
    />
    <HistoryDownloadModal
      v-if="modalStore.isModalOpen('historyDownload') && marketToDownload"
      :market="marketToDownload"
      :offer="offerDownload"
    />
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
import { h, ref, watch } from 'vue';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { lazyComponent } from '@/components/Common/lazyComponent';
import BaseModal from '@/components/Common/BaseModal.vue';
import { useModalStore } from '@/stores/modalStore';
import type { Market } from '@/types/contracts';

const HistoryDownloadModal = lazyComponent(
  () => import('./history/HistoryDownloadModal.vue'),
  'Download historical data',
  (state) =>
    h(
      BaseModal,
      { modalId: 'historyDownload', title: 'Download historical data' },
      () => state,
    ),
);
const IndicatorSearchModal = lazyComponent(
  () => import('./IndicatorSearchModal.vue'),
  'Indicator',
  (state) =>
    h(
      BaseModal,
      { modalId: 'indicatorSearch', title: 'Indicator' },
      () => state,
    ),
);
const RemoveMarketModal = lazyComponent(
  () => import('./RemoveMarketModal.vue'),
  'Remove Market',
  (state) =>
    h(
      BaseModal,
      { modalId: 'removeMarket', title: 'Remove Market' },
      () => state,
    ),
);
const SymbolFormModal = lazyComponent(
  () => import('./SymbolFormModal.vue'),
  'Market',
  (state) =>
    h(BaseModal, { modalId: 'symbolForm', title: 'Market' }, () => state),
);
const SymbolSearchModal = lazyComponent(
  () => import('./SymbolSearchModal.vue'),
  'Symbol',
  (state) =>
    h(BaseModal, { modalId: 'symbolSearch', title: 'Symbol' }, () => state),
);
const UploadDataModal = lazyComponent(
  () => import('./Upload/UploadDataModal.vue'),
  'Upload Data',
  (state) =>
    h(BaseModal, { modalId: 'uploadData', title: 'Upload Data' }, () => state),
);

defineOptions({
  name: 'TopBarModals',
});

const modalStore = useModalStore();
const marketToDownload = ref<Market | null>(null);
const offerDownload = ref(false);
const hasOpenedSymbolSearch = ref(false);
watch(
  () => modalStore.isModalOpen('symbolSearch'),
  (open) => {
    if (open) hasOpenedSymbolSearch.value = true;
  },
  { immediate: true },
);
const currentMarket = useCurrentMarketStore();
const marketToEdit = ref<Market | null>(null);
const marketToRemove = ref<Market | null>(null);
const marketToUpload = ref<Market | null>(null);

function onDownloadHistory(market: Market): void {
  if (market.source_type !== 'broker') return;
  marketToDownload.value = market;
  offerDownload.value = false;
  modalStore.openModal('historyDownload');
}

function onMarketCreated(market: Market): void {
  if (market.source_type !== 'broker') return;
  onDownloadHistory(market);
  offerDownload.value = true;
}

function onEditMarket(market: Market): void {
  marketToEdit.value = market;
  modalStore.openModal('symbolForm');
}

function onOpenSymbolFormModal(): void {
  marketToEdit.value = null;
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
    currentMarket.setMarket(marketToUpload.value);
    modalStore.closeModal();
  }
  marketToUpload.value = null;
}

function onMarketRemoved(): void {
  if (marketToRemove.value) {
    currentMarket.setMarket(marketToRemove.value);
    modalStore.closeModal();
  }
  marketToRemove.value = null;
}
</script>
