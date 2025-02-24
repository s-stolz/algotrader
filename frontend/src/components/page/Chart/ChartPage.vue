<template>
    <div>
        <div id="wrapper-select">
            <button id="symbol-button" @click="showSymbolSelectModal = true">
                {{ selectedSymbol?.symbol }}
            </button>

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

            <button id="indicator-button" @click="showIndicatorModal = true">
                Indicator
            </button>
        </div>

        <div id="chart-wrapper">
            <lightweight-chart
                id="candlestick-chart"
                ref="candlestickChart"
                type="candlestick"
                :data="data"
                :chartOptions="chartOptions"
                :seriesOptions="seriesOptions"
                :timeScaleOptions="timeScaleOptions"
            >
                <div id="indicator-wrapper"></div>
            </lightweight-chart>
        </div>

        <modal
            v-model:visible="showSymbolSelectModal"
            title="Symbol"
            closeOnBackdrop
            ref="symbolSearchModal"
        >
            <symbol-search
                :markets="markets"
                :selected-symbol="selectedSymbol"
                @update-symbol="updateSymbol"
                @add-symbol="addSymbol"
            />

            <template #footer>
                <button @click="showSymbolSelectModal = false" class="footer-close-modal">
                    Close
                </button>
            </template>
        </modal>

        <modal
            v-model:visible="showAddSymbolModal"
            title="New Symbol"
            closeOnBackdrop
            ref="addSymbolModal"
        >
            <symbol-form
                :newSymbol="newSymbol"
                ref="symbolForm"
                @add-symbol-successful="showAddSymbolModal = false"
            />

            <template #footer>
                <button
                    @click="this.$refs.symbolForm.addSymbol()"
                    class="footer-add-symbol"
                >
                    Add Symbol
                </button>

                <button @click="showAddSymbolModal = false" class="footer-close-modal">
                    Close
                </button>
            </template>
        </modal>

        <modal
            v-model:visible="showIndicatorModal"
            title="Indicator"
            closeOnBackdrop
            ref="indicatorModal"
        >
            <indicator-search
                :symbolID="selectedSymbol.symbol_id"
                :timeframe="selectedTimeframe.value"
            />
        </modal>
    </div>
</template>

<script>
import { createVNode, render, reactive } from "vue";
import LightweightChart from "@/components/LightweightChart.vue";
import SymbolSearch from "./SymbolSearch.vue";
import SymbolForm from "./SymbolForm.vue";
import IndicatorSearch from "./IndicatorSearch.vue";
import Indicator from "./Indicator.vue";
import Modal from "@/components/Modal.vue";
import Ticket from "@/utils/Ticket";

export default {
    name: "Chart",

    components: {
        "lightweight-chart": LightweightChart,
        "symbol-search": SymbolSearch,
        "symbol-form": SymbolForm,
        "indicator-search": IndicatorSearch,
        indicator: Indicator,
        modal: Modal,
    },

    data() {
        return {
            showSymbolSelectModal: false,
            showAddSymbolModal: false,
            showIndicatorModal: false,
            newSymbol: undefined,
            markets: [],
            selectedSymbol: null,
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
                { name: "2H", value: 120 },
                { name: "4H", value: 240 },
                { name: "1D", value: 1440 },
            ],
            chartOptions: {
                layout: {
                    textColor: "#d1d4dc",
                    background: { type: "solid", color: "transparent" },
                    panes: {
                        separatorColor: "rgba(96,96,96,0.3)",
                    },
                },
                grid: {
                    vertLines: {
                        color: "transparent",
                    },
                    horzLines: {
                        color: "transparent",
                    },
                },
                autoSize: true,
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
            indicatorCounter: 0,
            indicators: new Map(),
        };
    },

    methods: {
        requestMarkets() {
            fetch("/api/markets")
                .then((response) => response.json())
                .then((data) => {
                    this.markets = data;

                    if (this.markets.length > 0) {
                        this.selectedSymbol = this.markets[0];
                        this.requestCandles();
                    }
                });
        },

        setMinMove(minMove) {
            this.seriesOptions.priceFormat.minMove = minMove;
            this.seriesOptions.priceFormat.precision = Math.log10(1 / minMove);
        },

        requestCandles() {
            if (!this.selectedSymbol) return;

            fetch(
                `/api/candles/${this.selectedSymbol.symbol_id}/${this.selectedTimeframe.value}`
            )
                .then((response) => response.json())
                .then((data) => {
                    this.data = data.map((candle) => {
                        let utc = new Date(candle.timestamp).getTime() / 1000;
                        return {
                            time: utc,
                            open: candle.open,
                            high: candle.high,
                            low: candle.low,
                            close: candle.close,
                        };
                    });

                    // console.log(this.data);

                    this.setMinMove(this.selectedSymbol.min_move);
                    this.updateAllIdicators();
                });
        },

        updateSymbol(newSymbol) {
            this.selectedSymbol = newSymbol;
            this.requestCandles();
            this.$refs.symbolSearchModal.close();
            this.updateAllIdicators();
        },

        addSymbol(newSymbol) {
            this.$refs.symbolSearchModal.close();
            this.newSymbol = newSymbol;
            this.showAddSymbolModal = true;
        },

        handleMessage(message) {
            console.log(message);
            if (message.type == "indicator-info") {
                this.addIndicator(
                    message.data.id,
                    message.data.indicator_info,
                    message.data.indicator_data
                );
            }
        },

        updateAllIdicators() {
            this.indicators.forEach((val, key) => {
                console.log(val);
                console.log(this.selectedSymbol);
                let parameters = val.customParamerters;

                let message = new Ticket().fromObject({
                    receiver: "Backtester",
                    type: "get-indicator",
                    data: {
                        id: val.id,
                        name: val.props.info.name,
                        symbolID: this.selectedSymbol.symbol_id,
                        timeframe: this.selectedTimeframe.value,
                        parameters,
                    },
                });

                this.$wss.send(message);
            });
        },

        addIndicator(existingID, indicatorInfo, indicatorData) {
            if (existingID !== null) {
                this.updateIndicator(existingID, indicatorInfo, indicatorData);
                return;
            }
            const id = this.indicatorCounter++;

            if (this.indicators.has(id)) {
                console.warn(`Indicator with ID ${id} already exists.`);
                return;
            }

            const candlestickChart = this.$refs.candlestickChart.getChart();

            // Create a unique container for this indicator
            const container = document.createElement("div");
            document.getElementById("indicator-wrapper").appendChild(container);

            // Create reactive props
            const reactiveProps = reactive({
                chart: candlestickChart,
                data: indicatorData,
                info: indicatorInfo,
            });

            const indicatorVNode = createVNode(Indicator, {
                ...reactiveProps,
                onDestroy: () => this.removeIndicator(id),
                onUpdateParameters: (eventPayload) => {
                    let indicator = this.indicators.get(id);
                    indicator.customParamerters = eventPayload;
                    this.requestIndicator(id, reactiveProps.info.name, eventPayload);
                },
            });

            render(indicatorVNode, container);

            this.indicators.set(id, {
                id,
                container,
                vnode: indicatorVNode,
                props: reactiveProps,
            });
        },

        requestIndicator(id, name, parameters) {
            console.log(parameters);

            let message = new Ticket().fromObject({
                receiver: "Backtester",
                type: "get-indicator",
                data: {
                    id,
                    name,
                    symbolID: this.selectedSymbol.symbol_id,
                    timeframe: this.selectedTimeframe.value,
                    parameters,
                },
            });

            this.$wss.send(message);
        },

        removeIndicator(id) {
            const indicator = this.indicators.get(id);
            if (!indicator) {
                console.warn(`Indicator with ID ${id} does not exist.`);
                return;
            }

            render(null, indicator.container);
            indicator.container.remove();
            this.indicators.delete(id);
        },

        updateIndicator(id, newInfo, newData) {
            const indicator = this.indicators.get(id);
            if (!indicator) {
                console.warn(`Indicator with ID ${id} does not exist.`);
                return;
            }

            // Use an exposed method to update the data reactively
            const vnode = indicator.vnode.component;
            vnode.proxy.updateData(newData);

            // Update info prop directly (assuming this does not create circular reactivity)
            indicator.props.info = newInfo;

            // console.log(`Indicator ${id} updated reactively.`);
        },
    },

    mounted() {
        this.requestMarkets();
        this.requestCandles();

        this.$wss.on("message", (data) => {
            try {
                let message = JSON.parse(data);
                this.handleMessage(message);
            } catch (error) {
                console.error("Failed to parse message:", error);
            }
        });
    },
};
</script>

<style scoped>
#candlestick-chart {
    height: calc(100vh - 80px);
}

#wrapper-select {
    margin-bottom: 20px;
}

#market-select {
    margin-right: 20px;
}

#symbol-button,
#indicator-button {
    padding: 10px 15px;
}

#timeframe-select {
    padding: 10px 15px;
}

.footer-close-modal,
.footer-add-symbol {
    padding: 10px 15px;
    margin-bottom: 10px;
    margin-right: 10px;
}

#indicator-wrapper {
    position: absolute;
    top: 30px;
    left: 0;
    z-index: 999;
}
</style>
