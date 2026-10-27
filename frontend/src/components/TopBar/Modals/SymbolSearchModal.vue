<template>
  <DesignScope>
    <BaseModal
      ref="baseModal"
      :modalId="'symbolSearch'"
      :title="'Symbol'"
    >
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

        <n-scrollbar
          v-if="showEmptyMarketPromo || showNoSearchMatches"
          style="height: 300px"
        >
          <template v-if="showEmptyMarketPromo">
            <div class="empty-market-state">
              <n-button
                text
                id="add-market-button"
                aria-label="Add Market"
                @click.stop="onAddMarketClick()"
              >
                <n-icon size="24">
                  <AddCircleOutline />
                </n-icon>
              </n-button>
              <hr class="separator row-separator" />
              <div class="empty-state-card">
                <n-space
                  vertical
                  align="center"
                  :size="Number.parseInt(designTokens.space.md)"
                >
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
                    :color="designTokens.color.panel"
                    :background-color="designTokens.color.body"
                    error-correction-level="M"
                  />
                </n-space>
              </div>
              <n-text
                depth="3"
                class="affiliate-footnote-bottom"
                >*affiliate link</n-text
              >
            </div>
          </template>

          <template v-else-if="showNoSearchMatches">
            <n-button
              text
              id="add-market-button"
              aria-label="Add Market"
              @click.stop="onAddMarketClick()"
            >
              <n-icon size="24">
                <AddCircleOutline />
              </n-icon>
            </n-button>
            <div class="empty-state-card">
              <n-space
                vertical
                align="center"
                :size="Number.parseInt(designTokens.space.sm)"
              >
                <n-text>No symbols match your search.</n-text>
              </n-space>
            </div>
          </template>
        </n-scrollbar>

        <template v-else>
          <BaseDataTable :max-height="290">
            <tbody>
              <SymbolRow
                v-for="market of filteredMarketList"
                :key="market.symbol_id"
                :market="market"
                :is-selected="
                  market.symbol === currentMarketStore.symbol &&
                  market.exchange === currentMarketStore.exchange
                "
                @market-click="onMarketClick"
                @remove-market="$emit('remove-market', $event)"
                @upload-data="$emit('upload-data', $event)"
              />
            </tbody>
          </BaseDataTable>
          <n-button
            text
            id="add-market-button"
            aria-label="Add Market"
            class="add-market-row"
            @click.stop="onAddMarketClick()"
          >
            <n-icon size="24">
              <AddCircleOutline />
            </n-icon>
          </n-button>
        </template>
      </div>

      <template #footer>
        <n-button
          @click="closeModal"
          class="button-close"
          >Close</n-button
        >
      </template>
    </BaseModal>
  </DesignScope>
</template>

<script setup lang="ts">
import { designTokens } from '@/design/tokens';
import DesignScope from '@/components/Common/DesignScope.vue';
import { computed, ref } from 'vue';
import {
  NButton,
  NIcon,
  NInput,
  NQrCode,
  NScrollbar,
  NSpace,
  NText,
} from 'naive-ui';

import BaseDataTable from '@/components/Common/BaseDataTable.vue';
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

const filteredMarketList = computed(() =>
  marketsStore.all
    .filter((market) => market.symbol.includes(symbolInput.value.toUpperCase()))
    .sort((a, b) => a.symbol.localeCompare(b.symbol)),
);

const showEmptyMarketPromo = computed(() => marketsStore.all.length === 0);
const showNoSearchMatches = computed(
  () => filteredMarketList.value.length === 0 && marketsStore.all.length > 0,
);

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
  width: calc(100% - 2 * var(--design-space-lg));
  margin: var(--design-space-sm) var(--design-space-lg);
}

.row-separator {
  background-color: var(--design-color-border);
}

#add-market-button:hover {
  background-color: var(--design-color-hover);
}

#add-market-button {
  margin: auto;
  width: 100%;
  height: var(--design-control-large);
}

.add-market-row {
  background-color: var(--design-color-inset);
  border-top: 1px solid var(--design-color-border);
}

.empty-state-cta {
  font-size: var(--design-text-heading);
  margin: 0;
  padding: 0;
}

.empty-state-card {
  margin: var(--design-space-sm) var(--design-space-lg) var(--design-space-md);
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
  border-radius: var(--design-radius-panel);
  object-fit: cover;
  box-shadow: 0 0 0 1px var(--design-color-border);
}

.affiliate-footnote-bottom {
  font-size: var(--design-text-secondary);
  margin-bottom: var(--design-space-sm);
  align-self: center;
}
</style>
