<template>
    <div>
        <div v-if="this.parentChart === undefined" ref="chartContainer" class="chart-container">
            <div id="legend"></div>
            <slot></slot>
        </div>
    </div>
</template>

<script>
import { createChart } from "lightweight-charts";
import {
    LineSeries,
    AreaSeries,
    BarSeries,
    BaselineSeries,
    CandlestickSeries,
    HistogramSeries,
} from "lightweight-charts";

export default {
    name: "LightweightChart",

    props: {
        parentChart: {
            type: Object,
        },

        data: {
            type: Array,
            required: false,
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
            let ohlc = this.seriesDataMap.get("ohlc");
            ohlc["data"] = this.data;

            this.sliceBars(this.data, ohlc["series"]);
        },

        seriesOptions: {
            handler(newOptions) {
                if (this.seriesDataMap.size === 0) return;

                let ohlc = this.seriesDataMap.get("ohlc");
                ohlc.series.applyOptions(newOptions);
            },
            deep: true,
        },
    },

    expose: [
        "getChart",
        "remove",
        "addSeriesAndData",
        "updateOptions",
        "subscribeVisibleLogicalRangeChange",
        "unsubscribeVisibleLogicalRangeChange",
    ],

    data() {
        return {
            chart: null,
            seriesDataMap: new Map(),
            legend: null,
            crossHairTimeout: null,
            loadedBars: 5000,
            indicatorCounter: 0,
        };
    },

    methods: {
        getChart() {
            return this.chart || this.parentChart;
        },

        sliceBars(data, series) {
            let len = data.length;
            let start = Math.max(0, len - this.loadedBars);
            let slicedData = data.slice(start, len);
            series.setData(slicedData);
        },

        getchartSeriesConstructorName(type) {
            const seriesMap = {
                line: LineSeries,
                area: AreaSeries,
                bar: BarSeries,
                baseline: BaselineSeries,
                candlestick: CandlestickSeries,
                histogram: HistogramSeries,
            };
            return seriesMap[type] || null;
        },

        addSeriesAndData(data, seriesKey, type, seriesOptions, paneID = 0) {
            if (!this.chart || !data) {
                return;
            }

            const SeriesConstructor = this.getchartSeriesConstructorName(type);
            if (!SeriesConstructor) {
                console.error("Invalid series type:", type);
                return;
            }

            try {
                let series = this.chart.addSeries(
                    SeriesConstructor,
                    seriesOptions,
                    paneID
                );

                this.seriesDataMap.set(seriesKey, {
                    series,
                    data,
                });
                this.sliceBars(data, series);
            } catch (error) {
                console.error("Failed to add series:", error);
            }
        },

        remove() {
            if (!this.chart) {
                console.error("Chart instance is undefined. Cannot remove series.");
                return;
            }

            if (this.seriesDataMap.size === 0) {
                return;
            }

            this.seriesDataMap.forEach((value, key) => {
                this.chart.removeSeries(value["series"]);
                this.seriesDataMap.delete(key);
            });
        },

        onVisibleLogicalRangeChanged(newVisibleLogicalRange) {
            // TODO: Is triggered twice! Why?
            if (this.seriesDataMap.size === 0) return;

            this.seriesDataMap.forEach((value, key) => {
                const barsInfo = value["series"].barsInLogicalRange(
                    newVisibleLogicalRange
                );

                if (barsInfo !== null && barsInfo.barsBefore < 50) {
                    // Load additional price data
                    console.log("Loading additional price bars...");
                    this.loadedBars += 5000;
                    this.sliceBars(value["data"], value["series"]);
                }
            });
        },

        updateOptions(seriesKey, seriesOptions) {
            this.seriesDataMap.get(seriesKey).series.applyOptions(seriesOptions);
        },

        subscribeVisibleLogicalRangeChange() {
            if (!this.chart) {
                console.error(
                    "Chart instance is undefined. Cannot subscribe to range changes."
                );
                return;
            }

            this.chart
                .timeScale()
                .subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChanged);
        },

        unsubscribeVisibleLogicalRangeChange() {
            if (!this.chart) {
                console.error(
                    "Chart instance is undefined. Cannot unsubscribe from range changes."
                );
                return;
            }

            this.chart
                .timeScale()
                .unsubscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChanged);
        },
    },

    mounted() {
        this.legend = document.getElementById("legend");

        this.chart =
            this.parentChart || createChart(this.$refs.chartContainer, this.chartOptions);

        this.addSeriesAndData(this.data, "ohlc", this.type, this.seriesOptions);

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

        this.subscribeVisibleLogicalRangeChange();
    },

    beforeUnmount() {
        this.unsubscribeVisibleLogicalRangeChange();
    },
};
</script>

<style scoped>
#legend {
    position: absolute;
    top: 0;
    left: 0;
}

.chart-container {
    height: 100%;
    width: 100%;
    display: block;
    position: relative;
}
</style>
