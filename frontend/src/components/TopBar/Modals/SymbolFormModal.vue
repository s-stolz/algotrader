<template>
  <base-modal ref="symbolForm" :modalId="'symbolForm'" :title="'New Symbol'">
    <div id="new-symbol-input-wrapper">
      <n-input
        class="new-symbol-input text-uppercase"
        v-model:value="symbol"
        :status="validSymbol || symbol === undefined ? 'success' : 'error'"
        placeholder="Symbol"
      />

      <n-input
        class="new-symbol-input text-uppercase"
        v-model:value="exchange"
        :status="validExchange || exchange === undefined ? 'success' : 'error'"
        placeholder="Exchange"
      />

      <n-input-number
        class="new-symbol-input"
        v-model:value="minMove"
        min="0"
        step="0.0001"
      />

      <n-select
        class="new-symbol-input"
        v-model:value="marketType"
        placeholder="Market Type"
        :status="validMarketType || marketType === undefined ? 'success' : 'error'"
        :options="options"
      />
    </div>

    <template #footer>
      <n-button round class="new-symbol-button" @click="addSymbol"> Add Symbol </n-button>
    </template>
  </base-modal>
</template>

<script>
import { NInput, NInputNumber, NSelect, NButton } from "naive-ui";
import BaseModal from "@/components/Common/BaseModal.vue";

export default {
  name: "SymbolFormModal",

  components: { NInput, NInputNumber, NSelect, NButton, BaseModal },

  // props: {
  //   newSymbol: {
  //     type: String,
  //     default: "",
  //   },
  // },

  data() {
    return {
      symbol: undefined,
      exchange: undefined,
      minMove: 0.00001,
      marketType: undefined,
      options: [
        { label: "Forex", value: "Forex" },
        { label: "Crypto", value: "Crypto" },
        { label: "Stock", value: "Stock" },
      ],
    };
  },

  computed: {
    validSymbol() {
      return typeof this.symbol == "string" && this.symbol.trim() !== "";
    },

    validExchange() {
      return typeof this.exchange == "string" && this.exchange.trim() !== "";
    },

    validMinMove() {
      return typeof this.minMove == "number" && this.minMove > 0;
    },

    validMarketType() {
      return typeof this.marketType == "string" && this.marketType.trim !== "";
    },
  },

  methods: {
    addSymbol() {
      if (
        !this.validSymbol ||
        !this.validExchange ||
        !this.validMinMove ||
        !this.validMarketType
      ) {
        this.setInvalidInputs();
        console.error("Invalid Inputs!");
        return;
      }

      let newMarket = {
        symbol: this.symbol.toUpperCase().trim(),
        exchange: this.exchange.toUpperCase().trim(),
        minMove: this.minMove,
        marketType: this.marketType.trim(),
      };

      console.log("Adding new market:", newMarket);
      this.$refs.symbolForm.close();

      // TODO: Implement API call to add the new market
      //   fetch("/api/markets", {
      //     method: "PUT",
      //     headers: {
      //       "Content-Type": "application/json",
      //     },
      //     body: JSON.stringify(newMarket),
      //   })
      //     .then((response) => response.json())
      //     .then(() => {
      //       this.$emit("add-symbol-successful");
      //     });
    },

    setInvalidInputs() {
      if (!this.validSymbol) this.symbol = null;
      if (!this.validExchange) this.exchange = null;
      if (!this.validMinMove) this.minMove = 0.00001;
      if (!this.validMarketType) this.marketType = null;
    },
  },
};
</script>

<style scoped>
.new-symbol-input {
  width: calc(100% - 30px);
  margin: 10px 15px 0 15px;
}

.new-symbol-input:last-child {
  margin-bottom: 10px;
}

.new-symbol-button {
  width: 100%;
}

.text-uppercase ::v-deep input {
  text-transform: uppercase;
}
</style>
