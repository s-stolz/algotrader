<template>
  <base-modal ref="baseModal" :modalId="'symbolSearch'" :title="'Symbol'">
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
        <table>
          <tbody>
            <template v-for="market of filteredMarketList" :key="market.symbol_id">
              <symbol-row
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
  </base-modal>
</template>

<script>
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useMarketsStore } from "@/stores/marketsStore";
import { useCandlesticksStore } from "@/stores/candlesticksStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";

import { NScrollbar, NInput, NIcon, NButton } from "naive-ui";
import {
  SearchOutline,
  AddCircleOutline,
} from "@/icons";
import BaseModal from "@/components/Common/BaseModal.vue";
import SymbolRow from "./SymbolRow.vue";

export default {
  name: "SymbolSearchModal",

  components: {
    NScrollbar,
    NInput,
    NIcon,
    NButton,
    SearchOutline,
    AddCircleOutline,
    BaseModal,
    SymbolRow,
  },

  emits: ["open-symbol-form-modal", "remove-market", "upload-data"],

  data() {
    return {
      symbolInput: "",
      currentMarketStore: useCurrentMarketStore(),
      marketsStore: useMarketsStore(),
      candlesticksStore: useCandlesticksStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
    };
  },

  computed: {
    filteredMarketList() {
      return this.marketsStore.all
        .filter((market) => {
          return market.symbol.includes(this.symbolInput.toUpperCase());
        })
        .sort((a, b) => {
          if (a.symbol < b.symbol) return -1;
          if (a.symbol > b.symbol) return 1;
          return 0;
        });
    },
  },

  methods: {
    onMarketClick(market) {
      this.updateCurrentMarket(market);
      this.closeModal();
    },

    closeModal() {
      this.$refs.baseModal.close();
    },

    updateCurrentMarket(market) {
      this.currentMarketStore.setMarket(market);

      const symbolID = market.symbol_id;
      const timeframe = this.currentTimeframeStore.value;

      this.candlesticksStore.fetch(symbolID, timeframe);

      this.closeModal();
    },

    onAddMarketClick() {
      this.$emit("open-symbol-form-modal");
    },

    onKeypressEnter() {
      if (this.filteredMarketList.length === 0) {
        return;
      }

      this.updateCurrentMarket(this.filteredMarketList[0]);
    },
  },

  expose: ["updateCurrentMarket"],
};
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
</style>
