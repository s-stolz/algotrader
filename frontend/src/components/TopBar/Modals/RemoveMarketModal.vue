<template>
  <BaseModal ref="baseModal" :modalId="'removeMarket'" :title="'Remove Market'">
    <div>
      <div class="confirmation-content">
        <n-icon size="48" color="#ff6b6b">
          <WarningOutline />
        </n-icon>
        <h3>Are you sure you want to remove this market?</h3>
        <p v-if="market">
          <strong>{{ market.symbol }}</strong>
          <br>
          <span class="market-type">{{ market.market_type }}</span>
          {{ market.exchange }}
        </p>
        <p class="warning-text">
          This action cannot be undone. All associated data for this market will be permanently deleted.
        </p>
      </div>
    </div>

    <template #footer>
      <div class="modal-actions">
        <n-button @click="closeModal" class="button-cancel">Cancel</n-button>
        <n-button
          type="error"
          @click="confirmRemoveCandles"
          :loading="isRemoving"
          class="button-remove"
        >
          Remove Candles
        </n-button>
        <n-button
          type="error"
          @click="confirmRemove"
          :loading="isRemoving"
          class="button-remove"
        >
          Remove Market
        </n-button>
      </div>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NIcon } from 'naive-ui';

import { deleteCandles } from '@/api/candleClient';
import { deleteMarket } from '@/api/marketClient';
import BaseModal from '@/components/Common/BaseModal.vue';
import { WarningOutline } from '@/icons';
import { useMarketsStore } from '@/stores/marketsStore';
import type { Market } from '@/types/contracts';

defineOptions({
  name: 'RemoveMarketModal',
});

interface BaseModalExpose {
  close: () => void;
}

const props = defineProps<{
  market: Market;
}>();

const emit = defineEmits<{
  (event: 'market-removed', market: Market): void;
}>();

const marketsStore = useMarketsStore();
const baseModal = ref<BaseModalExpose | null>(null);
const isRemoving = ref(false);

function closeModal(): void {
  baseModal.value?.close();
  isRemoving.value = false;
}

async function tryRemoveMarketCandles(): Promise<boolean> {
  try {
    await deleteCandles(props.market.symbol, { exchange: props.market.exchange });
    return true;
  } catch (error) {
    console.error('Error removing market candles:', error);
    return false;
  }
}

async function confirmRemoveCandles(): Promise<void> {
  isRemoving.value = true;

  const removed = await tryRemoveMarketCandles();
  isRemoving.value = false;

  if (removed) {
    emit('market-removed', props.market);
    closeModal();
  }
}

async function tryRemoveMarket(): Promise<boolean> {
  try {
    await deleteMarket(props.market.symbol, { exchange: props.market.exchange });
    return true;
  } catch (error) {
    console.error('Error removing market:', error);
    return false;
  }
}

async function confirmRemove(): Promise<void> {
  isRemoving.value = true;

  const removed = await tryRemoveMarket();
  isRemoving.value = false;
  if (removed) {
    await marketsStore.fetch();
    closeModal();
  }
}
</script>

<style scoped>
.confirmation-content {
  text-align: center;
  padding: 20px;
}

p {
  margin: 12px 0;
  line-height: 20px;
}

.market-type {
  font-size: x-small;
  vertical-align: middle;
  text-transform: uppercase;
}

.warning-text {
  font-style: italic;
  font-size: small;
  margin-top: 20px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
