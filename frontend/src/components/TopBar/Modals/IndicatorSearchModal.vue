<template>
  <base-modal :modalId="'indicatorSearch'" :title="'Indicator'">
    <div>
      <span id="search-bar-wrapper">
        <n-input
          v-model:value="indicatorInput"
          id="indicator-input"
          autocomplete="off"
          placeholder="Indicator"
          round
          clearable
        >
          <template #prefix>
            <n-icon>
              <SearchOutline />
            </n-icon>
          </template>
        </n-input>
        <hr class="separator" />
      </span>

      <n-scrollbar style="height: 300px">
        <table>
          <tbody>
            <template v-for="(indicatorName, key) in filteredIndicators" :key="key">
              <tr @click="onApplyIndicator(indicatorName)">
                <td>
                  {{ indicatorName }}
                </td>
              </tr>

              <hr class="row-separator" />
            </template>
          </tbody>
        </table>
      </n-scrollbar>
    </div>
  </base-modal>
</template>

<script>
import BaseModal from "@/components/Common/BaseModal.vue";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
import { useIndicatorsStore } from "@/stores/indicatorsStore";

import { NScrollbar, NInput, NIcon } from "naive-ui";
import { SearchOutline } from "@/icons";

export default {
  name: "IndicatorSearchModal",

  components: {
    BaseModal,
    NScrollbar,
    NInput,
    NIcon,
    SearchOutline,
  },

  data() {
    return {
      indicatorInput: "",
      indicators: [],
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      indicatorsStore: useIndicatorsStore(),
    };
  },

  computed: {
    filteredIndicators() {
      return this.indicators
        .filter((indicator) =>
          indicator.toUpperCase().includes(this.indicatorInput.toUpperCase())
        )
        .sort((a, b) => a.localeCompare(b));
    },

    symbolID() {
      return this.currentMarketStore.symbol_id;
    },

    timeframe() {
      return this.currentTimeframeStore.value;
    },
  },

  mounted() {
    this.$wss.on("message", this.wssMessageHandler);
    this.$wss.send("Backtester", "list-indicators");
  },

  beforeUnmount() {
    this.$wss.off("message", this.wssMessageHandler);
  },

  methods: {
    wssMessageHandler(data) {
      const message = this.parseMessage(data);
      this.handleMessage(message);
    },

    parseMessage(data) {
      try {
        return JSON.parse(data);
      } catch (error) {
        console.error("Failed to parse message:", error);
      }
    },

    handleMessage(message) {
      if (message.type === "list-indicators-response")
        this.handleListIndicatorsResponse(message.data);
    },

    handleListIndicatorsResponse(indicators) {
      this.indicators = indicators;
    },

    onApplyIndicator(indicatorName) {
      const data = {
        id: null,
        name: indicatorName,
        symbol_id: this.symbolID,
        timeframe: this.timeframe,
      };

      this.indicatorsStore.requestIndicator(data);
    },
  },
};
</script>

<style scoped>
#search-bar-wrapper {
  position: sticky;
  top: -10px;
}

#indicator-input {
  width: calc(100% - 30px);
  margin: 8px 15px;
}

table {
  width: 100%;
}

tr {
  padding: 5px 15px;
  width: calc(100% - 30px);
  display: flex;
  cursor: pointer;
}

td {
  line-height: 20px;
  padding: 10px 0;
}

.row-separator {
  border: none;
  height: 1px;
  background-color: #a0a0a029;
  margin: 0;
}

tr:hover {
  background-color: #36363661;
}
</style>
