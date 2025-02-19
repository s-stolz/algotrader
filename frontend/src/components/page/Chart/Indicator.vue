<template>
    <div class="indicator-wrapper">
        <div class="indicator-info">
            <p>{{ info.name }}</p>
            <button class="indicator-remove-button" @click="removeIndicator">x</button>
            <button
                class="indicator-settings-button"
                @click="showIndicatorSettingsModal = true"
            >
                s
            </button>
        </div>

        <lightweight-chart
            id="indicator-chart"
            ref="indicatorChart"
            :parentChart="chart"
        />

        <modal
            v-model:visible="showIndicatorSettingsModal"
            :title="info.name"
            closeOnBackdrop
            ref="indicatorSettingsModal"
        >
            <table>
                <tr
                    v-for="(parameter, key_param) in parameters"
                    :key="key_param"
                    class="indicator-parameter"
                >
                    <td class="">
                        <p>
                            {{ key_param }}
                        </p>
                    </td>

                    <td>
                        <select
                            v-if="
                                parameter.type == 'string' && parameter.options !== null
                            "
                            v-model="parameter.value"
                        >
                            <option
                                v-for="(option, key_option) in parameter.options"
                                :key="key_option"
                                :value="option"
                            >
                                {{ option }}
                            </option>
                        </select>

                        <input
                            v-else-if="
                                parameter.type == 'string' && parameter.options === null
                            "
                            type="text"
                            v-model="parameter.value"
                        />

                        <input
                            v-else-if="
                                parameter.type == 'int' || parameter.type == 'float'
                            "
                            type="number"
                            v-model="parameter.value"
                            :min="parameter.min"
                            :max="parameter.max"
                            :step="parameter.step"
                        />
                    </td>
                </tr>
            </table>
        </modal>
    </div>
</template>

<script>
import LightweightChart from "@/components/LightweightChart.vue";
import Modal from "@/components/Modal.vue";

export default {
    name: "Indicator",

    expose: ["updateData"],
    emits: ["update-parameters", "destroy"],

    components: {
        "lightweight-chart": LightweightChart,
        modal: Modal,
    },

    props: {
        chart: {
            type: Object,
            required: true,
        },
        data: {
            type: Array,
            required: true,
        },
        info: {
            type: Object,
            required: true,
        },
    },

    watch: {
        parameters: {
            handler(newParameters) {
                this.$emit("update-parameters", newParameters);
            },
            deep: true,
        },

        // data: {
        //     deep: true, // Ensure nested changes are detected
        //     immediate: true, // Run on initial render
        //     handler(newData) {
        //         if (this.$refs.indicatorChart) {
        //             console.log("WATCH DATA");
        //             this.updateData(newData);
        //         }
        //     },
        // },
    },

    data() {
        return {
            showIndicatorSettingsModal: false,
            // localData: [...this.data],
            parameters: Object.fromEntries(
                Object.entries(this.info.parameters).map(([paramKey, paramValue]) => [
                    paramKey,
                    { ...paramValue, value: paramValue.default }, // Add `value` key
                ])
            ),
        };
    },

    methods: {
        removeIndicator() {
            this.$refs.indicatorChart.remove();
            this.$emit("destroy", this);
        },

        updateData(newData) {
            this.$refs.indicatorChart.remove();
            let panes = this.chart.panes();
            let paneID = this.info.overlay ? 0 : panes.length;

            for (let output of Object.keys(newData[0])) {
                if (output == "timestamp") {
                    continue;
                }

                const transformedData = newData.map((x) => ({
                    value: x[output],
                    time: Math.floor(new Date(x.timestamp).getTime() / 1000),
                }));

                this.$refs.indicatorChart.addSeriesAndData(
                    transformedData,
                    output,
                    this.info.outputs[output].type,
                    this.info.outputs[output].plotOptions || {},
                    paneID
                );
            }
        },
    },

    mounted() {
        // console.log(this.info);

        this.updateData(this.data);
    },
};
</script>

<style scoped>
/* .indicator-wrapper {
    display: block;
} */

.indicator-info {
    display: flex;
}

.parameter-header {
    padding: 0 15px;
}

.indicator-info p,
.indicator-info button {
    margin-top: 0;
    margin-bottom: 10px;
}

.indicator-remove-button,
.indicator-settings-button {
    margin-left: 8px;
    height: 20px;
    width: 20px;
}

.indicator-parameter {
    display: flex;
    padding: 0 15px;
}

.indicator-parameter td {
    width: 100px;
    margin: auto;
}

.indicator-parameter td input {
    padding: 10px 15px;
    width: 100px;
    outline: none;
    border: 1px solid gray;
    border-radius: 8px;
}

.indicator-parameter td select {
    padding: 10px 15px;
    margin: 0;
    width: 100px;
    border-radius: 8px;
    background: none;
    outline: 1px solid gray;
}
</style>
