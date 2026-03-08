<template>
  <n-popselect
    :default-value="timeframes[0].value"
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
import { TIMEFRAME_OPTIONS } from "@/utils/timeframes";

import { NPopselect, NButton } from "naive-ui";

export default {
  name: "TimeframeDropdown",

  components: {
    NPopselect,
    NButton,
  },

  data() {
    return {
      currentTimeframeStore: useCurrentTimeframeStore(),
      timeframes: TIMEFRAME_OPTIONS,
    };
  },

  methods: {
    onTimeframeChange(value, option) {
      this.currentTimeframeStore.setCurrentTimeframe(option);
    },
  },
};
</script>

<style scoped>
.timeframe-button {
  width: 80px;
}
</style>
