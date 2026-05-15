<template>
  <BaseModal ref="baseModal" :modalId="'symbolSearch'" :title="'Symbol'">
    <div>
      <span id="search-bar">
        <n-input
          v-model:value="symbolInput"
          id="symbol-input"
          autocomplete="off"
          placeholder="Symbol"
          @keyup.enter="onKeypressEnter"
          :input-props="{ style: 'text-transform: uppercase;' }"
          round
          clearable
        >
          <template #prefix>
            <n-icon>
              <SearchOutline />
            </n-icon>
          </template>
        </n-input>
      </span>
      <hr class="separator" />

      <n-scrollbar style="height: 300px">
        <template v-if="showEmptyMarketPromo">
          <div class="empty-market-state">
            <n-button
              text
              id="add-market-button"
              @click.stop="onAddMarketClick()"
            >
              <n-icon size="24">
                <AddCircleOutline />
              </n-icon>
            </n-button>
            <hr class="separator row-separator" />
            <div class="empty-state-card">
              <n-space vertical align="center" :size="12">
                <h3 class="empty-state-cta">Don’t have a broker yet?</h3>
                <n-button
                  tag="a"
                  :href="affiliateLink"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="button-close"
                >
                  Get Started with IC Trading*
                </n-button>
                <n-qr-code
                  class="affiliate-qr"
                  :value="affiliateLink"
                  :size="108"
                  color="#171a1f"
                  background-color="#dadee2"
                  error-correction-level="M"
                />
              </n-space>
            </div>
            <n-text depth="3" class="affiliate-footnote-bottom">*affiliate link</n-text>
          </div>
        </template>

        <template v-else-if="showNoSearchMatches">
          <n-button
            text
            id="add-market-button"
            @click.stop="onAddMarketClick()"
          >
            <n-icon size="24">
              <AddCircleOutline />
            </n-icon>
          </n-button>
          <div class="empty-state-card">
            <n-space vertical align="center" :size="8">
              <n-text>No symbols match your search.</n-text>
            </n-space>
          </div>
        </template>

        <table v-else>
          <tbody>
            <template v-for="market of filteredMarketList" :key="market.symbol_id">
              <SymbolRow
                :market="market"
                @market-click="onMarketClick"
                @remove-market="$emit('remove-market', $event)"
                @upload-data="$emit('upload-data', $event)"
              />
              <hr class="separator row-separator" />
            </template>

            <n-button text id="add-market-button" @click.stop="onAddMarketClick()">
              <n-icon size="24">
                <AddCircleOutline />
              </n-icon>
            </n-button>
          </tbody>
        </table>
      </n-scrollbar>
    </div>

    <template #footer>
      <n-button @click="closeModal" class="button-close">Close</n-button>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { NButton, NIcon, NInput, NQrCode, NScrollbar, NSpace, NText } from 'naive-ui';

import BaseModal from '@/components/Common/BaseModal.vue';
import { AddCircleOutline, SearchOutline } from '@/icons';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { Market } from '@/types/contracts';

import SymbolRow from './SymbolRow.vue';

defineOptions({
  name: 'SymbolSearchModal',
});

interface BaseModalExpose {
  close: () => void;
}

const emit = defineEmits<{
  (event: 'open-symbol-form-modal'): void;
  (event: 'remove-market', market: Market): void;
  (event: 'upload-data', market: Market): void;
}>();

const baseModal = ref<BaseModalExpose | null>(null);
const symbolInput = ref('');
const affiliateLink = 'https://www.ictrading.com?camp=86158';
const currentMarketStore = useCurrentMarketStore();
const marketsStore = useMarketsStore();

const filteredMarketList = computed(() => marketsStore.all
  .filter((market) => market.symbol.includes(symbolInput.value.toUpperCase()))
  .sort((a, b) => a.symbol.localeCompare(b.symbol)));

const showEmptyMarketPromo = computed(() => marketsStore.all.length === 0);
const showNoSearchMatches = computed(() => (
  filteredMarketList.value.length === 0 && marketsStore.all.length > 0
));

function closeModal(): void {
  baseModal.value?.close();
}

function updateCurrentMarket(market: Market): void {
  currentMarketStore.setMarket(market);
  closeModal();
}

function onMarketClick(market: Market): void {
  updateCurrentMarket(market);
  closeModal();
}

function onAddMarketClick(): void {
  emit('open-symbol-form-modal');
}

function onKeypressEnter(): void {
  if (filteredMarketList.value.length === 0) {
    return;
  }

  updateCurrentMarket(filteredMarketList.value[0]);
}

defineExpose({ updateCurrentMarket });
</script>

<style scoped>
#symbol-input {
  width: calc(100% - 30px);
  margin: 8px 15px;
}

.row-separator {
  background-color: #a0a0a029;
}

table {
  width: 100%;
}

tr {
  padding: 5px 15px;
  width: calc(100% - 30px);
  display: flex;
  justify-content: space-between;
  cursor: pointer;
}

td {
  line-height: 20px;
}

.market-type {
  font-size: x-small;
  vertical-align: middle;
}

tr:hover,
#add-market-button:hover {
  background-color: #36363661;
}

#add-market-button {
  margin: auto;
  width: 100%;
  height: 40px;
}

.empty-state-cta {
  margin: 0;
  padding: 0;
}

.empty-state-card {
  margin: 8px 15px 12px;
  display: flex;
  justify-content: center;
  text-align: center;
  flex: 1;
  align-items: center;
}

.empty-market-state {
  min-height: 300px;
  display: flex;
  flex-direction: column;
}

.affiliate-qr {
  width: 108px;
  height: 108px;
  border-radius: 8px;
  object-fit: cover;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.affiliate-footnote-bottom {
  font-size: 9px;
  margin-bottom: 10px;
  align-self: center;
}
</style>
