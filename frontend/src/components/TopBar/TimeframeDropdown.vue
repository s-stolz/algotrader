<template>
  <n-popselect
    default-value="1M"
    scrollable
    style="width: 80px; height: 150px;"
    @update:value="onTimeframeChange"
    :options="timeframes"
  >
    <n-button
      round
      class="timeframe-button"
    >
      {{ currentTimeframeStore.label }}
    </n-button>
  </n-popselect>
</template>

<script>
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCandlesticksStore } from "@/stores/candlesticksStore";

import { NPopselect, NButton } from "naive-ui";

export default {
  name: "TimeframeDropdown",

  components: {
    NPopselect,
    NButton
  },

  data() {
    return {
      currentTimeframeStore: useCurrentTimeframeStore(),
      currentMarketStore: useCurrentMarketStore(),
      candlesticksStore: useCandlesticksStore(),
      timeframes: [
        { label: "1M", value: 1 },
        { label: "5M", value: 5 },
        { label: "15M", value: 15 },
        { label: "30M", value: 30 },
        { label: "1H", value: 60 },
        { label: "2H", value: 120 },
        { label: "4H", value: 240 },
        { label: "D", value: 1440 },
      ],
    };
  },

  methods: {
    onTimeframeChange(value, option) {
      this.currentTimeframeStore.setCurrentTimeframe(option);
      
      const symbolID  = this.currentMarketStore.symbol_id;
      this.candlesticksStore.fetch(symbolID, value);
    },
  },
};
</script>

<style scoped>
.timeframe-button {
  width: 80px;
}
</style>