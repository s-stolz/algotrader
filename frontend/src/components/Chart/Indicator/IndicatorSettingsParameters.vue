<template>
  <n-scrollbar style="height: 300px">
    <table>
      <tr
        v-for="(parameter, key) in indicatorParameters"
        :key="key"
        class="indicator-parameter"
      >
        <td>
          <p>
            {{ replaceUnderscoreWithSpace(key) }}
          </p>
        </td>

        <td>
          <n-select
            v-if="isStringWithOptions(parameter)"
            v-model:value="parameter.value"
            @update:value="onParameterUpdate"
            :options="parameter.options.map((opt) => ({ label: opt, value: opt }))"
          />

          <n-input
            v-else-if="isStringWithoutOptions(parameter)"
            v-model:value="parameter.value"
            @update:value="onParameterUpdate"
          />

          <n-input-number
            v-else-if="isNumber(parameter)"
            v-model:value="parameter.value"
            :min="parameter.min"
            :max="parameter.max"
            :step="parameter.step"
            @update:value="onParameterUpdate"
          />
        </td>
      </tr>
    </table>
  </n-scrollbar>
</template>

<script>
import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";

import { NScrollbar, NInput, NInputNumber, NSelect } from "naive-ui";

export default {
  name: "IndicatorSettingsParameters",

  components: {
    NScrollbar,
    NInput,
    NInputNumber,
    NSelect,
  },

  props: {
    indicator: {
      type: Object,
      required: true,
    },
  },

  data() {
    return {
      indicatorsStore: useIndicatorsStore(),
      currentMarketStore: useCurrentMarketStore(),
      currentTimeframeStore: useCurrentTimeframeStore(),
      updateDelay: 200,
      updateTimeout: null,
    };
  },

  computed: {
    symbolID() {
      return this.currentMarketStore.symbol_id;
    },

    timeframe() {
      return this.currentTimeframeStore.value;
    },

    indicatorId() {
      return this.indicator.id;
    },

    indicatorInfo() {
      return this.indicator?.info;
    },

    indicatorParameters() {
      return this.indicator?.parameters;
    },
  },

  methods: {
    replaceUnderscoreWithSpace(str) {
      return str.replace(/_/g, " ");
    },

    isStringWithOptions(parameter) {
      return parameter.type === "string" && parameter.options !== null;
    },
    isStringWithoutOptions(parameter) {
      return parameter.type === "string" && parameter.options === null;
    },
    isNumber(parameter) {
      return parameter.type === "int" || parameter.type === "float";
    },

    onParameterUpdate() {
      if (this.updateTimeout) {
        clearTimeout(this.updateTimeout);
      }

      this.updateTimeout = setTimeout(() => {
        this.updateTimeout = null;
        this.handleParameterUpdate();
      }, this.updateDelay);
    },

    handleParameterUpdate() {
      const customParameters = this.buildCustomParameters();
      this.updateIndicatorStoreParameters(this.indicatorId, customParameters);

      const requestData = {
        id: this.indicatorId,
        name: this.indicatorInfo.name,
        symbol_id: this.symbolID,
        timeframe: this.timeframe,
        parameters: customParameters,
      };
      this.requestIndicatorWithNewParameters(requestData);
    },

    updateIndicatorStoreParameters(indicatorId, newParameters) {
      this.indicatorsStore.updateIndicatorParameters(indicatorId, newParameters);
    },

    requestIndicatorWithNewParameters(requestData) {
      this.indicatorsStore.requestIndicator(requestData);
    },

    buildCustomParameters() {
      const customParameters = {};

      for (const [key, param] of Object.entries(this.indicatorParameters)) {
        customParameters[key] = { value: param.value };
      }
      return customParameters;
    },
  },
};
</script>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
}

.indicator-parameter td,
.output-style-option td {
  padding: 5px 15px;
  border-bottom: 1px solid #333;
}

.indicator-parameter p {
  margin: 0;
  color: #ccc;
  text-transform: capitalize;
}
</style>
