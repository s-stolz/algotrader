<template>
  <div id="wrapper-select">
    <n-button primary round @click="modalStore.openModal('symbolSearch')">
      {{ currentSymbol }}
    </n-button>

    <TimeframeDropdown />

    <n-button round @click="modalStore.openModal('indicatorSearch')">Indicator</n-button>
    <n-button round data-testid="open-backtest-runs" @click="modalStore.openModal('backtestRuns')">
      <template #icon>
        <n-icon>
          <ListOutline />
        </n-icon>
      </template>
      Backtest Runs
    </n-button>

    <TopBarModals />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NButton, NIcon } from 'naive-ui';

import TimeframeDropdown from '@/components/TopBar/TimeframeDropdown.vue';
import TopBarModals from '@/components/TopBar/Modals/TopBarModals.vue';
import { ListOutline } from '@/icons';
import { useCurrentMarketStore } from '@/stores/currentMarketStore';
import { useModalStore } from '@/stores/modalStore';

defineOptions({
  name: 'TheTopBar',
});

const currentMarketStore = useCurrentMarketStore();
const modalStore = useModalStore();
const currentSymbol = computed(() => currentMarketStore.symbol);
</script>

<style scoped>
#wrapper-select {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
