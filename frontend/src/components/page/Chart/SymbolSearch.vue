<template>
    <div>
        <span id="search-bar">
            <label for="symbol-input"><img src="/search.svg" alt="Search" /></label>
            <input id="symbol-input" type="search" v-model="symbolInput.symbol" autocomplete="off" placeholder="Symbol"
                @keyup.enter="inputKeypressEnter" />
        </span>
        <hr class="search-seperator" />

        <div class="table-container" :class="{ 'has-scroll': filteredMarkets.length > 8 }">
            <table>
                <tbody>
                    <template v-for="symbol of filteredMarkets" :key="symbol.symbol_id">
                        <tr @click="symbolSelected(symbol)">
                            <td>{{ symbol.symbol }}</td>
                            <td>
                                <span class="market-type">{{ symbol.market_type }}</span>
                                {{ symbol.exchange }}
                            </td>
                        </tr>
                        <hr class="row-seperator" />
                    </template>

                    <tr @click="addMarket()">
                        <td id="add-market">+</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <hr class="search-seperator" />
    </div>
</template>

<script>
export default {
    name: "SymbolSearch",

    emits: ["update-symbol", "add-symbol"],

    props: {
        selectedSymbol: {
            type: Object,
            required: true,
        },

        markets: {
            type: Array,
            required: true,
        },
    },

    data() {
        return {
            symbolInput: { ...this.selectedSymbol },
            newSymbol: {
                symbol: "",
                market: "",
            },
        };
    },

    computed: {
        filteredMarkets() {
            return this.markets
                .filter((symbol) => {
                    return symbol.symbol.includes(this.symbolInput.symbol.toUpperCase());
                })
                .sort((a, b) => {
                    // Sort by the `symbol` property alphabetically
                    if (a.symbol < b.symbol) return -1;
                    if (a.symbol > b.symbol) return 1;
                    return 0;
                });
        },
    },

    methods: {
        symbolSelected(symbol) {
            this.symbolInput = symbol;
            this.$emit("update-symbol", symbol);
        },

        inputKeypressEnter() {
            this.symbolInput = this.filteredMarkets[0];
            this.$emit("update-symbol", this.symbolInput);
        },

        addMarket() {
            this.$emit("add-symbol", this.symbolInput.symbol);
        },
    },
};
</script>

<style scoped>
#search-bar {
    display: flex;
    line-height: 49px;
}

#search-bar img {
    width: 28px;
    height: 28px;
    vertical-align: middle;
    margin-left: 15px;
}

#symbol-input {
    width: 100%;
    margin-top: 8px;
    border: none;
    text-transform: uppercase;
}

input[type="search"]::-webkit-search-cancel-button {
    -webkit-appearance: none;
    height: 24px;
    width: 24px;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23777'><path d='M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z'/></svg>");
}

.search-seperator {
    border: none;
    height: 1px;
    background-color: #ddd;
}

.row-seperator {
    border: none;
    height: 1px;
    background-color: #a0a0a029;
    margin: 0;
}

.table-container {
    max-height: 300px;
    overflow-y: hidden;
    border-radius: 4px;
}

.table-container.has-scroll {
    overflow-y: auto;
    /* Add scrolling only when needed */
}

.table-container::-webkit-scrollbar {
    width: 12px;
    height: 12px;
}

.table-container::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 6px;
    border: 2px solid transparent;
    background-clip: padding-box;
}

.table-container::-webkit-scrollbar-thumb:hover {
    background: #555;
}

table {
    width: 100%;
    height: 400px;
    overflow: hidden;
    padding: 0;
}

table tbody {
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

tr:hover {
    background-color: #36363661;
}

.market-type {
    font-size: x-small;
    vertical-align: middle;
}

#add-market {
    width: 100%;
    height: 40px;
    background: none;
    font-size: 20px;
    border-radius: 0;
    text-align: center;
}
</style>
