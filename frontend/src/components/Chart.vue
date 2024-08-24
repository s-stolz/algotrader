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
    name: "Chart",

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
            this.series.setData(this.data);
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
        };
    },

    methods: {
        getchartSeriesConstructorName(type) {
            return `add${type.charAt(0).toUpperCase() + type.slice(1)}Series`;
        },

        addSeriesAndData() {
            const seriesConstructor = this.getchartSeriesConstructorName(this.type);
            this.series = this.chart[seriesConstructor](this.seriesOptions);
            this.series.setData(this.data);
        },

        resizeHandler() {
            if (!this.chart || !this.$refs.chartContainer.value) return;
            const dimensions = this.$refs.chartContainer.value.getBoundingClientRect();
            this.chart.resize(dimensions.width, dimensions.height);
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
            const validCrosshairPoint = !(
                param === undefined ||
                param.time === undefined ||
                param.point.x < 0 ||
                param.point.y < 0
            );
            if (!validCrosshairPoint) return;

            let bar = this.data.find((bar) => bar.time === param.time);

            if (!bar) return;
            this.legend.innerHTML = `O: ${bar.open} | H: ${bar.high} | L: ${bar.low} | C: ${bar.close}`;
        });

        this.chart.timeScale().fitContent();

        if (this.autosize) {
            window.addEventListener("resize", this.resizeHandler);
        }
    },
};
</script>

<style scoped>
#chart-container {
    height: 600px;
    width: 100%;
    display: block;
}
</style>
