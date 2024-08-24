<template>
    <div>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Exchange</th>
                    <th>Min Move</th>
                    <th>Market Type</th>
                    <th>Candle Count</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="market in markets" :key="market.symbol_id">
                    <td>{{ market.symbol }}</td>
                    <td>{{ market.exchange }}</td>
                    <td>{{ market.min_move }}</td>
                    <td>{{ market.market_type }}</td>
                    <td>
                        {{ market.candle_count }}
                    </td>
                </tr>

                <tr>
                    <td>
                        <input type="text" v-model="symbol" placeholder="Symbol" />
                    </td>

                    <td>
                        <input type="text" v-model="exchange" placeholder="Exchange" />
                    </td>

                    <td>
                        <input type="number" v-model="minMove" />
                    </td>

                    <td>
                        <select v-model="marketType">
                            <option value="forex">Forex</option>
                            <option value="crypto">Crypto</option>
                            <option value="stock">Stock</option>
                        </select>
                    </td>

                    <td>
                        <button @click="addMarket">Add</button>
                    </td>
                </tr>
            </tbody>
        </table>

        <button @click="requestNewCandles()">Pull All Data</button>
    </div>
</template>

<script>
export default {
    name: "DataPage",

    data() {
        return {
            symbol: "",
            exchange: "",
            minMove: 0.00001,
            marketType: "",
            markets: [],
            pullSymbol: null,
        };
    },

    methods: {
        addMarket() {
            console.log(this.symbol, this.exchange, this.minMove, this.marketType);
            let newMarket = {
                symbol: this.symbol,
                exchange: this.exchange,
                minMove: this.minMove,
                marketType: this.marketType,
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
                    console.log(data);
                    this.markets.push(newMarket);
                });
        },

        requestMarkets() {
            fetch("/api/markets")
                .then((response) => response.json())
                .then((data) => {
                    console.log(data);
                    this.markets = data;
                });
        },

        requestNewCandles() {
            fetch("/api/candles/update")
                .then((response) => response.json())
                .then((data) => {
                    console.log(data);
                });
        },
    },

    mounted() {
        this.requestMarkets();
    },
};
</script>

<style scoped></style>
