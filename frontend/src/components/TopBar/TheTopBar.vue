<template>
  <div id="wrapper-select">
    <n-button primary round @click="modalStore.openModal('symbolSearch')">
      {{ currentSymbol }}
    </n-button>

    <timeframe-dropdown />

    <n-button round @click="modalStore.openModal('indicatorSearch')">Indicator</n-button>

    <top-bar-modals />
  </div>
</template>

<script>
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useModalStore } from "@/stores/modalStore";

import { NButton } from "naive-ui";
import TimeframeDropdown from "@/components/TopBar/TimeframeDropdown.vue";
import TopBarModals from "@/components/TopBar/Modals/TopBarModals.vue";

export default {
  name: "TheTopBar",

  components: {
    NButton,
    TimeframeDropdown,
    TopBarModals,
  },

  data() {
    return {
      currentMarketStore: useCurrentMarketStore(),
      modalStore: useModalStore(),
    };
  },

  computed: {
    currentSymbol() {
      return this.currentMarketStore.symbol;
    },
  },
};
</script>

<style scoped>
#wrapper-select {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
</style>
