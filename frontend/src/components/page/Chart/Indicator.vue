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
            <div>
                <div id="indicator-tab-wrapper">
                    <span id="indicator-tab">
                        <button
                            @click="showTab = 'settings'"
                            :class="{ active: showTab == 'settings' }"
                        >
                            Settings
                        </button>

                        <button
                            @click="showTab = 'style'"
                            :class="{ active: showTab == 'style' }"
                        >
                            Style
                        </button>
                    </span>

                    <hr class="separator" />
                </div>

                <table v-if="showTab == 'settings'">
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
                                    parameter.type == 'string' &&
                                    parameter.options !== null
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
                                    parameter.type == 'string' &&
                                    parameter.options === null
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

                <table v-else-if="showTab == 'style'">
                    <template
                        v-for="(output, outputKey) in info.outputs"
                        :key="outputKey"
                    >
                        <tr class="output-style-header">
                            <td colspan="2">
                                <h3>{{ outputKey }}</h3>
                            </td>
                        </tr>

                        <template
                            v-for="(value, styleKey) in output.plotOptions"
                            :key="styleKey"
                        >
                            <!-- Handle direct primitive values -->
                            <tr
                                v-if="typeof value !== 'object' || value === null"
                                class="output-style-option"
                            >
                                <td>{{ styleKey }}</td>

                                <td v-if="typeof value === 'string'">
                                    <input
                                        type="color"
                                        @change="updateStyles(outputKey)"
                                        v-model="styles[outputKey].plotOptions[styleKey]"
                                    />
                                </td>

                                <td v-else-if="typeof value === 'number'">
                                    <input
                                        type="number"
                                        min="1"
                                        @change="updateStyles(outputKey)"
                                        v-model="styles[outputKey].plotOptions[styleKey]"
                                    />
                                </td>
                            </tr>

                            <!-- Handle nested objects like priceFormat -->
                            <template v-else>
                                <tr class="output-style-subheader">
                                    <td colspan="2">
                                        <strong>{{ styleKey }}</strong>
                                    </td>
                                </tr>
                                <tr
                                    v-for="(subValue, subKey) in value"
                                    :key="subKey"
                                    class="output-style-option"
                                >
                                    <td>{{ subKey }}</td>

                                    <td v-if="typeof subValue === 'number'">
                                        <input
                                            type="number"
                                            :min="1"
                                            @change="updateStyles(outputKey)"
                                            v-model="
                                                styles[outputKey].plotOptions[styleKey][
                                                    subKey
                                                ]
                                            "
                                        />
                                    </td>

                                    <td v-else-if="typeof subValue === 'string'">
                                        <input
                                            type="text"
                                            @change="updateStyles(outputKey)"
                                            v-model="
                                                styles[outputKey].plotOptions[styleKey][
                                                    subKey
                                                ]
                                            "
                                        />
                                    </td>
                                </tr>
                            </template>
                        </template>
                    </template>
                </table>
            </div>
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
    },

    data() {
        return {
            showIndicatorSettingsModal: false,
            showTab: "settings",
            parameters: Object.fromEntries(
                Object.entries(this.info.parameters).map(([paramKey, paramValue]) => [
                    paramKey,
                    { ...paramValue, value: paramValue.default }, // Add `value` key
                ])
            ),
            styles: Object.assign({}, this.info.outputs),
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

        updateStyles(output) {
            this.$refs.indicatorChart.updateOptions(
                output,
                this.styles[output].plotOptions
            );
        },
    },

    mounted() {
        // console.log(this.info);

        this.updateData(this.data);
    },
};
</script>

<style scoped>
#indicator-tab-wrapper {
    position: sticky;
    top: -15px;
    /* padding-top: 15px; */
    background: #131722;
}

#indicator-tab button {
    padding: 10px 20px;
    border-radius: 0;
    margin-bottom: -3px;
}

#indicator-tab button.active {
    border-bottom: 3px solid #ddd;
}

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

.indicator-parameter,
.output-style-option {
    display: flex;
    padding: 0 15px;
}

.indicator-parameter td,
.output-style-option td {
    width: 180px;
    margin: auto;
}

.indicator-parameter td input,
.output-style-option td input {
    padding: 10px 15px;
    width: 100px;
    outline: none;
    border: 1px solid gray;
    border-radius: 8px;
}

.output-style-option td input[type="color"] {
    padding: 0;
    width: 30px;
    height: 30px;
    border: none;
    outline: none;
    cursor: pointer;
}

.indicator-parameter td select {
    padding: 10px 15px;
    margin: 0;
    width: 100px;
    border-radius: 8px;
    background: none;
    outline: 1px solid gray;
}

.separator {
    border: none;
    height: 1px;
    background-color: #ddd;
    margin: 0;
}

tr.output-style {
    padding: 0 15px;
}

.output-style-subheader strong,
tr.output-style-header h3 {
    padding: 0 15px;
    margin: 20px 0 0;
}
</style>
