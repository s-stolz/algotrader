<template>
  <div id="new-symbol-input-wrapper">
    <input
      class="new-symbol-input text-uppercase"
      type="text"
      v-model="symbol"
      placeholder="Symbol"
    />

    <hr />

    <input
      class="new-symbol-input text-uppercase"
      type="text"
      v-model="exchange"
      placeholder="Exchange"
    />

    <hr />

    <input
      class="new-symbol-input"
      type="number"
      v-model="minMove"
      min="0"
      step="0.0001"
    />
    <hr />
    <input
      list="market-options"
      class="new-symbol-input"
      v-model="marketType"
      placeholder="Market Type"
    />
    <datalist id="market-options">
      <option value="Forex"></option>
      <option value="Crypto"></option>
      <option value="Stock"></option>
    </datalist>
  </div>
</template>

<script>
export default {
  name: "SymbolFormModal",

  props: {
    newSymbol: {
      type: String,
      default: "",
    },
  },

  data() {
    return {
      symbol: this.newSymbol,
      exchange: "",
      minMove: 0.00001,
      marketType: "",
      symbolChanged: false, // Tracks if the input has been modified
    };
  },

  methods: {
    addSymbol() {
      if (
        !this.validSymbol ||
        !this.validExchange ||
        !this.validMinMove ||
        !this.validMarketType
      ) {
        console.error("Invalid Inputs!");
        return;
      }

      console.log(this.symbol, this.exchange, this.minMove, this.marketType);
      let newMarket = {
        symbol: this.symbol.toUpperCase().trim(),
        exchange: this.exchange.toUpperCase().trim(),
        minMove: this.minMove,
        marketType: this.marketType.trim(),
      };
      fetch("/api/markets", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(newMarket),
      })
        .then((response) => response.json())
        .then((data) => {
          this.$emit("add-symbol-successful");
        });
    },
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
};
</script>

<style scoped>
#new-symbol-input-wrapper {
  display: block;
}

.new-symbol-input {
  width: calc(100% - 30px);
  margin: 5px 0;
  border: none;
}

.new-symbol-input.valid-input,
.new-symbol-input.invalid-input {
  width: calc(100% - 34px);
  margin: 3px 0;
}

hr {
  border: none;
  height: 1px;
  background-color: #a0a0a029;
  margin: 0;
}

.text-uppercase {
  text-transform: uppercase;
}

.valid-input {
  background-color: 1px solid rgb(13, 103, 13);
}

.invalid-input {
  border: 1px solid rgb(65, 8, 8);
}
</style>
