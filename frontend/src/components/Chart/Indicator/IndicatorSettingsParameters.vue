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

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { NScrollbar, NInput, NInputNumber, NSelect } from "naive-ui";

import { useIndicatorsStore } from "@/stores/indicatorsStore";
import { useCurrentMarketStore } from "@/stores/currentMarketStore";
import { useCurrentTimeframeStore } from "@/stores/currentTimeframeStore";
import type {
  IndicatorParameterEntry,
  IndicatorParameterValues,
  IndicatorStoreQuery,
  StoreIndicator,
} from "@/stores/indicatorsStore";
import type { IndicatorRequestBody } from "@/types/contracts";

interface StringParameterWithOptions extends IndicatorParameterEntry {
  type: "string";
  value?: string;
  options: string[];
}

interface StringParameterWithoutOptions extends IndicatorParameterEntry {
  type: "string";
  value?: string;
}

interface NumericParameter extends IndicatorParameterEntry {
  type: "int" | "float";
  value?: number | null;
  min?: number;
  max?: number;
  step?: number;
}

defineOptions({
  name: "IndicatorSettingsParameters",
});

const props = defineProps<{
  indicator: StoreIndicator;
}>();

const indicatorsStore = useIndicatorsStore();
const currentMarketStore = useCurrentMarketStore();
const currentTimeframeStore = useCurrentTimeframeStore();
const updateDelay = 200;
const updateTimeout = ref<ReturnType<typeof setTimeout> | null>(null);

const symbol = computed(() => currentMarketStore.symbol);
const exchange = computed(() => currentMarketStore.exchange);
const timeframe = computed(() => currentTimeframeStore.value);
const indicatorParameters = computed(() => props.indicator.parameters);

function replaceUnderscoreWithSpace(str: string): string {
  return str.replace(/_/g, " ");
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isStringWithOptions(
  parameter: IndicatorParameterEntry,
): parameter is StringParameterWithOptions {
  return (
    parameter.type === "string" &&
    isStringArray(parameter.options) &&
    parameter.options.length > 0
  );
}

function isStringWithoutOptions(
  parameter: IndicatorParameterEntry,
): parameter is StringParameterWithoutOptions {
  return parameter.type === "string" && !isStringArray(parameter.options);
}

function isNumber(parameter: IndicatorParameterEntry): parameter is NumericParameter {
  return parameter.type === "int" || parameter.type === "float";
}

function onParameterUpdate(): void {
  if (updateTimeout.value) {
    clearTimeout(updateTimeout.value);
  }

  updateTimeout.value = setTimeout(() => {
    updateTimeout.value = null;
    handleParameterUpdate();
  }, updateDelay);
}

function handleParameterUpdate(): void {
  const customParameters = buildCustomParameters();
  updateIndicatorStoreParameters(props.indicator._id, customParameters);

  const queryParams: IndicatorStoreQuery = {
    symbol: symbol.value,
    timeframe: timeframe.value,
    limit: 500,
  };
  if (exchange.value) {
    queryParams.exchange = exchange.value;
  }
  const body: IndicatorRequestBody = {
    parameters: customParameters,
  };

  requestIndicatorWithNewParameters(
    props.indicator._id,
    props.indicator.indicatorId,
    queryParams,
    body,
  );
}

function updateIndicatorStoreParameters(
  _id: string,
  newParameters: IndicatorParameterValues,
): void {
  indicatorsStore.updateIndicatorParameters(_id, newParameters);
}

function requestIndicatorWithNewParameters(
  _id: string,
  indicatorId: number,
  queryParams: IndicatorStoreQuery,
  body: IndicatorRequestBody,
): void {
  void indicatorsStore.requestIndicator(_id, indicatorId, queryParams, body);
}

function buildCustomParameters(): IndicatorParameterValues {
  const customParameters: IndicatorParameterValues = {};

  for (const [key, param] of Object.entries(indicatorParameters.value)) {
    if (param.value !== undefined) {
      customParameters[key] = param.value;
    }
  }
  return customParameters;
}

onBeforeUnmount(() => {
  if (updateTimeout.value) {
    clearTimeout(updateTimeout.value);
  }
});
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
