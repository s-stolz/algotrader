<template>
    <div>
        <span id="search-bar">
            <label for="symbol-input"><img src="/search.svg" alt="Search" /></label>
            <input
                id="indicator-input"
                type="search"
                v-model="indicatorInput"
                autocomplete="off"
                placeholder="Indicator"
            />
        </span>
        <hr class="search-seperator" />

        <div
            class="table-container"
            :class="{ 'has-scroll': filteredIndicators.length > 8 }"
        >
            <table>
                <tbody>
                    <span
                        v-for="(indicator, key) in filteredIndicators"
                        :key="key"
                        @click="applyIndicator(indicator)"
                    >
                        <tr>
                            <p>
                                {{ indicator }}
                            </p>
                        </tr>

                        <hr class="row-seperator" />
                    </span>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script>
import Ticket from "@/utils/Ticket";

export default {
    name: "IndicatorSearch",

    props: {
        symbolID: {
            type: Number,
        },
        timeframe: {
            type: Number,
        },
    },

    data() {
        return {
            indicatorInput: "",
            indicatorList: [],
        };
    },

    methods: {
        handleMessage(message) {
            if (message.type === "list-indicators-response")
                this.listIndicatorsResponse(message.data);
        },

        listIndicatorsResponse(indicatorList) {
            this.indicatorList = indicatorList;
        },

        applyIndicator(indicator) {
            let message = new Ticket().fromObject({
                receiver: "Backtester",
                type: "get-indicator",
                data: {
                    name: indicator,
                    symbolID: this.symbolID,
                    timeframe: this.timeframe,
                },
            });

            this.$wss.send(message);
        },
    },

    computed: {
        filteredIndicators() {
            // return this.indicatorList;
            return this.indicatorList.filter((indicator) =>
                indicator.toUpperCase().includes(this.indicatorInput.toUpperCase())
            );
        },
    },

    mounted() {
        let message = new Ticket().fromObject({
            receiver: "Backtester",
            type: "list-indicators",
        });
        this.$wss.send(message);

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
#search-bar {
    display: flex;
    line-height: 49px;
}

input[type="search"]::-webkit-search-cancel-button {
    -webkit-appearance: none;
    height: 24px;
    width: 24px;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23777'><path d='M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z'/></svg>");
}

#search-bar img {
    width: 28px;
    height: 28px;
    vertical-align: middle;
    margin-left: 15px;
}

#indicator-input {
    width: 100%;
    margin-top: 8px;
    border: none;
}

.table-container {
    max-height: 300px;
    overflow-y: hidden;
    border-radius: 4px;
}
.table-container.has-scroll {
    overflow-y: auto; /* Add scrolling only when needed */
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

.row-seperator {
    border: none;
    height: 1px;
    background-color: #a0a0a029;
    margin: 0;
}

tr:hover,
button#add-market:hover {
    background-color: #36363661;
}
</style>
