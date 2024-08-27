<template>
    <header>
        <button>Charts</button>

        <button>Data</button>
    </header>

    <!-- <hr /> -->

    <main>
        <select v-model="selectedSymbol" @change="requestCandles">
            <option v-for="market in markets" :key="market.symbol_id" :value="market">
                {{ market.symbol }}
            </option>
        </select>

        <select
            name="timeframe"
            id="timeframe-select"
            v-model="selectedTimeframe"
            @change="requestCandles"
        >
            <option
                v-for="timeframe in timeframes"
                :key="timeframe.value"
                :value="timeframe"
            >
                {{ timeframe.name }}
            </option>
        </select>

        <lightweight-chart
            type="candlestick"
            :data="data"
            :chartOptions="chartOptions"
            :seriesOptions="seriesOptions"
            :timeScaleOptions="timeScaleOptions"
        />
    </main>
</template>

<script>
import LightweightChart from "./components/LightweightChart.vue";

export default {
    components: {
        "lightweight-chart": LightweightChart,
    },

    data() {
        return {
            markets: [],
            selectedSymbol: undefined,
            selectedTimeframe: {
                name: "1M",
                value: 1,
            },
            timeframes: [
                { name: "1M", value: 1 },
                { name: "5M", value: 5 },
                { name: "15M", value: 15 },
                { name: "30M", value: 30 },
                { name: "1H", value: 60 },
            ],
            chartOptions: {
                layout: {
                    textColor: "#d1d4dc",
                    background: { type: "solid", color: "transparent" },
                },
                grid: {
                    vertLines: {
                        color: "transparent",
                    },
                    horzLines: {
                        color: "transparent",
                    },
                },
            },
            timeScaleOptions: {
                timeVisible: true,
                secondsVisible: false,
            },
            seriesOptions: {
                priceFormat: {
                    type: "price",
                    minMove: 0.00001,
                },
            },
            data: [],
        };
    },

    methods: {
        requestMarkets() {
            // Fetch markets from the backend
            fetch("/api/markets")
                .then((response) => response.json())
                .then((data) => {
                    this.markets = data;
                    this.selectedSymbol = this.markets[0];
                    this.requestCandles();
                });
        },

        setMinMove(minMove) {
            this.seriesOptions = {
                priceFormat: {
                    type: "price",
                    minMove: minMove,
                },
            };
        },

        requestCandles() {
            // Fetch markets from the backend
            fetch(
                `/api/candles/${this.selectedSymbol.symbol_id}/${this.selectedTimeframe.value}`
            )
                .then((response) => response.json())
                .then((data) => {
                    this.data = data.map((candle) => {
                        return {
                            time: Date.parse(candle.timestamp) / 1000,
                            open: candle.open,
                            high: candle.high,
                            low: candle.low,
                            close: candle.close,
                        };
                    });

                    this.setMinMove(this.selectedSymbol.min_move);
                });
        },
    },

    mounted() {
        this.requestMarkets();
    },
};
</script>

<style scoped>
header button {
    margin: 10px 8px;
    padding: 10px 20px;
    border: none;
    border-radius: 10px;
    background: none;
    color: white;
    font-size: 20px;
    font-weight: 600;
}

header button:hover {
    background: rgba(41, 43, 51, 0.5);
}
</style>
