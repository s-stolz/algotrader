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
            <template v-for="(indicator) in filteredIndicators" :key="indicator.id">
              <tr @click="onApplyIndicator(indicator)">
                <td>
                  {{ indicator.name }}
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
          indicator.name.toUpperCase().includes(this.indicatorInput.toUpperCase()),
        )
        .sort((a, b) => a.name.localeCompare(b.name));
    },

    symbolID() {
      return this.currentMarketStore.symbol_id;
    },

    timeframe() {
      return this.currentTimeframeStore.value;
    },
  },

  mounted() {
    this.getIndicators();
  },

  methods: {
    getIndicators() {
      fetch("/api/indicator-api/indicators")
        .then((response) => response.json())
        .then((data) => {
          this.indicators = data;
          console.log(data);
        })
        .catch((error) => {
          console.error("Error fetching indicators:", error);
        });
    },

    onApplyIndicator(indicator) {
      const queryParams = {
        symbol_id: this.symbolID,
        timeframe: this.timeframe,
        limit: 5000,
      };

      this.indicatorsStore.requestIndicator(null, indicator.id, queryParams, {});
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
