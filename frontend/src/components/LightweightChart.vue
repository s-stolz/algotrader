<template>
    <div>
        <div
            v-if="this.parentChart === undefined"
            ref="chartContainer"
            id="chart-container"
        >
            <div id="legend"></div>
            <slot></slot>
            <div id="indicator-wrapper"></div>
        </div>
    </div>
</template>

<script>
import { createChart } from "lightweight-charts";

export default {
    name: "LightweightChart",

    props: {
        parentChart: {
            type: Object,
        },

        data: {
            type: Array,
            required: true,
        },

        chartOptions: {
            type: Object,
        },

        type: {
            type: String,
            default: "line",
        },

        seriesOptions: {
            type: Object,
        },

        timeScaleOptions: {
            type: Object,
        },
    },

    watch: {
        data() {
            this.sliceBars();
        },

        seriesOptions(newOptions) {
            if (!this.series) return;
            this.series.applyOptions(newOptions);
        },
    },

    expose: ["getChart", "remove"],

    data() {
        return {
            chart: null,
            series: null,
            legend: null,
            crossHairTimeout: null,
            loadedBars: 5000,
            autosize: true,
            indicators: new Map(),
            indicatorCounter: 0,
        };
    },

    methods: {
        getChart() {
            return this.chart || this.parentChart;
        },

        sliceBars() {
            let len = this.data.length;
            let start = Math.max(0, len - this.loadedBars);
            let slicedData = this.data.slice(start, len);
            this.series.setData(slicedData);
        },

        getchartSeriesConstructorName(type) {
            return `add${type.charAt(0).toUpperCase() + type.slice(1)}Series`;
        },

        addSeriesAndData() {
            if (!this.chart) {
                console.error("Chart instance is undefined. Cannot add series.");
                return;
            }

            const seriesConstructor = this.getchartSeriesConstructorName(this.type);

            try {
                this.series = this.chart[seriesConstructor](this.seriesOptions);
                this.sliceBars();
            } catch (error) {
                console.error("Failed to add series:", error);
            }
        },

        remove() {
            if (!this.chart) {
                console.error("Chart instance is undefined. Cannot remove series.");
                return;
            }

            if (!this.series) {
                console.error("Series is undefined. Cannot remove series.");
                return;
            }

            this.chart.removeSeries(this.series);
            this.series = null;
        },

        resizeHandler() {
            if (!this.chart || !this.$refs.chartContainer) return;
            const dimensions = this.$refs.chartContainer.getBoundingClientRect();
            this.chart.resize(dimensions.width, dimensions.height);
        },

        onVisibleLogicalRangeChanged(newVisibleLogicalRange) {
            // TODO: Is triggered twice! Why?
            if (!this.series) return;
            const barsInfo = this.series.barsInLogicalRange(newVisibleLogicalRange);
            // console.log(barsInfo);
            if (barsInfo !== null && barsInfo.barsBefore < 50) {
                // Load additional price data
                // console.log("Loading additional price bars...");
                this.loadedBars += 5000;
                this.sliceBars();
            }
        },
    },

    mounted() {
        this.legend = document.getElementById("legend");

        this.chart =
            this.parentChart || createChart(this.$refs.chartContainer, this.chartOptions);

        this.addSeriesAndData();

        if (this.priceScaleOptions) {
            this.chart.priceScale().applyOptions(this.priceScaleOptions);
        }

        if (this.timeScaleOptions) {
            this.chart.timeScale().applyOptions(this.timeScaleOptions);
        }

        this.chart.subscribeCrosshairMove((param) => {
            try {
                if (this.crossHairTimeout != null) {
                    clearTimeout(this.crossHairTimeout);
                }

                const validCrosshairPoint = !(
                    param === undefined ||
                    param.time === undefined ||
                    param.point.x < 0 ||
                    param.point.y < 0
                );
                if (!validCrosshairPoint || this.parentChart !== undefined) return;

                this.crossHairTimeout = setTimeout(() => {
                    let bar = this.data.find((bar) => bar.time === param.time);

                    if (!bar) return;
                    this.legend.innerHTML = `O: ${bar.open} | H: ${bar.high} | L: ${bar.low} | C: ${bar.close}`;

                    this.crossHairTimeout = null;
                }, 10);
            } catch (error) {
                console.log("Catch");
            }
        });

        this.chart
            .timeScale()
            .subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChanged);

        if (this.autosize) {
            window.addEventListener("resize", this.resizeHandler);
        }
    },

    beforeUnmount() {
        this.chart
            .timeScale()
            .unsubscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChanged);

        window.removeEventListener("resize", this.resizeHandler);
    },
};
</script>

<style scoped>
#legend {
    position: absolute;
    top: 0;
    left: 0;
}

#chart-container {
    height: calc(100vh - 80px);
    width: 100%;
    display: block;
    position: relative;
}
</style>
