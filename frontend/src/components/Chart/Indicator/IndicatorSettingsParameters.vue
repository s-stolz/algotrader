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
      this.updateIndicatorStoreParameters(this.indicator._id, customParameters);

      const queryParams = {
        symbol_id: this.symbolID,
        timeframe: this.timeframe,
        limit: 5000,
      };
      const body = {
        parameters: customParameters,
      };

      this.requestIndicatorWithNewParameters(
        this.indicator._id,
        this.indicator.indicatorId,
        queryParams,
        body,
      );
    },

    updateIndicatorStoreParameters(_id, newParameters) {
      this.indicatorsStore.updateIndicatorParameters(_id, newParameters);
    },

    requestIndicatorWithNewParameters(_id, indicatorId, queryParams, body) {
      this.indicatorsStore.requestIndicator(_id, indicatorId, queryParams, body);
    },

    buildCustomParameters() {
      const customParameters = {};

      for (const [key, param] of Object.entries(this.indicatorParameters)) {
        customParameters[key] = param.value;
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
