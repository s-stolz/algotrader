<template>
  <div>
    <the-top-bar />
    <chart-area
      id="chart-area"
      ref="chartArea"
    />
  </div>
</template>

<script>
import { useMarketsStore } from "@/stores/marketsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";

import TheTopBar from "@/components/TopBar/TheTopBar.vue";
import ChartArea from "@/components/Chart/ChartArea.vue";

export default {
  name: "ChartView",

  components: {
    TheTopBar,
    ChartArea,
  },

  data() {
    return {
      marketsStore: useMarketsStore(),
      currentMarketStore: useCurrentMarketStore(),
    };
  },

  async created() {
    await this.initializeChartView();
  },

  methods: {
    async initializeChartView() {
      await this.fetchMarketsAndInitCurrent();
    },

    async fetchMarketsAndInitCurrent() {
      await this.marketsStore.fetch();

      if (this.marketsStore.all.length === 0) {
        return;
      }

      this.currentMarketStore.setMarket(this.marketsStore.all[0]);
    },
  },
};
</script>

<style scoped>
#chart-area {
  height: calc(100vh - 80px);
}
</style>
