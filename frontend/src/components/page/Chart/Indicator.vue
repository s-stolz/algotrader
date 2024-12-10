<template>
    <div>
        <lightweight-chart ref="indicatorChart" :parentChart="chart" :data="localData" />

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

        <modal
            v-model:visible="showIndicatorSettingsModal"
            :title="info.name"
            closeOnBackdrop
            ref="indicatorSettingsModal"
        >
            <table>
                <template v-for="(output, key_out) in info.outputs" :key="key_out">
                    <h3 class="parameter-header">{{ key_out }}</h3>
                    <tr
                        v-for="(parameter, key_param) in output['parameters']"
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
                                v-model="parameterValues[key_param]"
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
                                v-model="parameterValues[key_param]"
                            />

                            <input
                                v-else-if="parameter.type == 'int'"
                                type="number"
                                v-model="parameterValues[key_param]"
                                :min="parameter.min"
                                :max="parameter.max"
                                :step="parameter.step"
                            />
                        </td>
                    </tr>
                </template>
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
        parameterValues: {
            handler(newParameters) {
                console.log(newParameters);
                this.$emit("update-parameters", newParameters);
            },
            deep: true,
        },
        data: {
            deep: true, // Ensure nested changes are detected
            immediate: true, // Run on initial render
            handler(newData) {
                if (this.$refs.indicatorChart) {
                    this.localData = [...newData];
                }
            },
        },
    },

    data() {
        return {
            showIndicatorSettingsModal: false,
            parameterValues: this.getParameterValues(),
            localData: [...this.data],
        };
    },

    methods: {
        removeIndicator() {
            this.$refs.indicatorChart.remove();
            this.$emit("destroy", this);
        },

        getParameterValues() {
            let values = {};
            console.log(this.info.outputs);
            for (const [key_out, output] of Object.entries(this.info.outputs)) {
                for (const [key_param, parameter] of Object.entries(output.parameters)) {
                    values[key_param] = parameter.default;
                }
            }
            return values;
        },

        updateData(newData) {
            this.localData = [...newData];
        },
    },
};
</script>

<style scoped>
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
    padding: auto;
    margin: auto;
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
}
</style>
