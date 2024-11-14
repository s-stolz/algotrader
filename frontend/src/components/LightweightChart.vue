<template>
    <div>
        <div ref="chartContainer" id="chart-container">
            <div id="legend"></div>
        </div>
    </div>
</template>

<script>
import { createChart } from "lightweight-charts";

export default {
    name: "LightweightChart",

    props: {
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

    data() {
        return {
            chart: null,
            series: null,
            legend: null,
            crossHairTimeout: null,
            loadedBars: 5000,
            autosize: true,
        };
    },

    methods: {
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
            const seriesConstructor = this.getchartSeriesConstructorName(this.type);
            this.series = this.chart[seriesConstructor](this.seriesOptions);
            this.series.setData(this.data);
        },

        resizeHandler() {
            if (!this.chart || !this.$refs.chartContainer) return;
            const dimensions = this.$refs.chartContainer.getBoundingClientRect();
            this.chart.resize(dimensions.width, dimensions.height);
        },

        onVisibleLogicalRangeChanged(newVisibleLogicalRange) {
            const barsInfo = this.series.barsInLogicalRange(newVisibleLogicalRange);
            // if there less than 50 bars to the left of the visible area
            if (barsInfo !== null && barsInfo.barsBefore < 50) {
                // try to load additional historical data and prepend it to the series data
                console.log("add additional bars");
                this.loadedBars += 5000;
                this.sliceBars();
            }
        },
    },

    mounted() {
        this.legend = document.getElementById("legend");
        this.chart = createChart(
            document.getElementById("chart-container"),
            this.chartOptions
        );

        this.addSeriesAndData();

        if (this.priceScaleOptions) {
            this.chart.priceScale().applyOptions(this.priceScaleOptions);
        }

        if (this.timeScaleOptions) {
            this.chart.timeScale().applyOptions(this.timeScaleOptions);
        }

        this.chart.subscribeCrosshairMove((param) => {
            if (this.crossHairTimeout != null) {
                clearTimeout(this.crossHairTimeout);
            }

            const validCrosshairPoint = !(
                param === undefined ||
                param.time === undefined ||
                param.point.x < 0 ||
                param.point.y < 0
            );
            if (!validCrosshairPoint) return;

            this.crossHairTimeout = setTimeout(() => {
                let bar = this.data.find((bar) => bar.time === param.time);

                if (!bar) return;
                this.legend.innerHTML = `O: ${bar.open} | H: ${bar.high} | L: ${bar.low} | C: ${bar.close}`;

                this.crossHairTimeout = null;
            }, 10);
        });

        this.chart
            .timeScale()
            .subscribeVisibleLogicalRangeChange(this.onVisibleLogicalRangeChanged);

        this.chart.timeScale().fitContent();

        if (this.autosize) {
            window.addEventListener("resize", this.resizeHandler);
        }
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
    height: calc(100vh - 120px);
    width: 100%;
    display: block;
    position: relative;
}
</style>
