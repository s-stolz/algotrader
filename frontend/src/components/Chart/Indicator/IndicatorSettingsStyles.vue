<template>
  <n-scrollbar style="height: 300px">
    <table>
      <template v-for="(output, outputKey) in indicatorInfo.outputs" :key="outputKey">
        <tr class="output-style-header">
          <td colspan="2">
            <n-h3 prefix="bar">{{ outputKey }}</n-h3>
          </td>
        </tr>

        <template v-for="(value, styleKey) in output.plotOptions" :key="styleKey">
          <!-- Handle direct primitive values -->
          <tr
            v-if="typeof value !== 'object' || value === null"
            class="output-style-option"
          >
            <td>{{ styleKey }}</td>

            <td v-if="typeof value === 'string'">
              <n-color-picker
                :value="getStringStyleValue(outputKey, styleKey)"
                @update:value="(newValue) => setStyleValue(outputKey, styleKey, newValue)"
              />
            </td>

            <td v-else-if="typeof value === 'number'">
              <n-input-number
                min="1"
                :value="getNumberStyleValue(outputKey, styleKey)"
                @update:value="(newValue) => setStyleValue(outputKey, styleKey, newValue)"
              />
            </td>
          </tr>

          <!-- Handle nested objects like priceFormat -->
          <template v-else-if="isJsonStyleObject(value)">
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
                <n-input-number
                  :min="0"
                  :value="getNestedNumberStyleValue(outputKey, styleKey, subKey)"
                  @update:value="
                    (newValue) => setNestedStyleValue(outputKey, styleKey, subKey, newValue)
                  "
                />
              </td>

              <td v-else-if="typeof subValue === 'string'">
                <n-input
                  :value="getNestedStringStyleValue(outputKey, styleKey, subKey)"
                  @update:value="
                    (newValue) => setNestedStyleValue(outputKey, styleKey, subKey, newValue)
                  "
                />
              </td>
            </tr>
          </template>
        </template>
      </template>
    </table>
  </n-scrollbar>
</template>

<script setup lang="ts">
import { reactive, watch } from "vue";
import { NScrollbar, NH3, NColorPicker, NInput, NInputNumber } from "naive-ui";

import type { IndicatorInfo, JsonObject, JsonValue } from "@/types/contracts";
import type { ChartSeriesOptions } from "@/utils/chart";

import type { IndicatorStyleUpdatePayload } from "./types";

type StyleKey = string | number;
type EditableStyleValue = string | number | null;

interface OutputStyleState {
  plotOptions: JsonObject;
}

defineOptions({
  name: "IndicatorSettingsStyles",
});

const props = defineProps<{
  indicatorInfo: IndicatorInfo;
}>();

const emit = defineEmits<{
  "update-styles": [payload: IndicatorStyleUpdatePayload];
}>();

const styles = reactive<Record<string, OutputStyleState>>({});

function toStyleKey(key: StyleKey): string {
  return String(key);
}

function isJsonStyleObject(value: JsonValue | undefined): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function initializeStyles(): void {
  for (const key of Object.keys(styles)) {
    delete styles[key];
  }

  for (const [outputKey, output] of Object.entries(props.indicatorInfo.outputs)) {
    styles[outputKey] = {
      plotOptions: { ...(output.plotOptions || {}) },
    };
  }
}

function getOutputPlotOptions(outputKey: StyleKey): JsonObject {
  const normalizedOutputKey = toStyleKey(outputKey);

  if (!styles[normalizedOutputKey]) {
    styles[normalizedOutputKey] = { plotOptions: {} };
  }

  return styles[normalizedOutputKey].plotOptions;
}

function getStringStyleValue(outputKey: StyleKey, styleKey: StyleKey): string {
  const value = getOutputPlotOptions(outputKey)[toStyleKey(styleKey)];
  return typeof value === "string" ? value : "";
}

function getNumberStyleValue(outputKey: StyleKey, styleKey: StyleKey): number | null {
  const value = getOutputPlotOptions(outputKey)[toStyleKey(styleKey)];
  return typeof value === "number" ? value : null;
}

function getNestedStyleObject(outputKey: StyleKey, styleKey: StyleKey): JsonObject {
  const plotOptions = getOutputPlotOptions(outputKey);
  const normalizedStyleKey = toStyleKey(styleKey);
  const existing = plotOptions[normalizedStyleKey];

  if (isJsonStyleObject(existing)) {
    return existing;
  }

  const nested: JsonObject = {};
  plotOptions[normalizedStyleKey] = nested;
  return nested;
}

function getNestedStringStyleValue(
  outputKey: StyleKey,
  styleKey: StyleKey,
  subKey: StyleKey,
): string {
  const value = getNestedStyleObject(outputKey, styleKey)[toStyleKey(subKey)];
  return typeof value === "string" ? value : "";
}

function getNestedNumberStyleValue(
  outputKey: StyleKey,
  styleKey: StyleKey,
  subKey: StyleKey,
): number | null {
  const value = getNestedStyleObject(outputKey, styleKey)[toStyleKey(subKey)];
  return typeof value === "number" ? value : null;
}

function setStyleValue(
  outputKey: StyleKey,
  styleKey: StyleKey,
  value: EditableStyleValue,
): void {
  getOutputPlotOptions(outputKey)[toStyleKey(styleKey)] = value;
  emitStyles(outputKey);
}

function setNestedStyleValue(
  outputKey: StyleKey,
  styleKey: StyleKey,
  subKey: StyleKey,
  value: EditableStyleValue,
): void {
  getNestedStyleObject(outputKey, styleKey)[toStyleKey(subKey)] = value;
  emitStyles(outputKey);
}

function emitStyles(outputKey: StyleKey): void {
  const normalizedOutputKey = toStyleKey(outputKey);
  emit("update-styles", {
    outputKey: normalizedOutputKey,
    styles: { ...getOutputPlotOptions(normalizedOutputKey) } as ChartSeriesOptions,
  });
}

watch(
  () => props.indicatorInfo,
  initializeStyles,
  { immediate: true },
);
</script>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
}

table tr td {
  padding: 5px 15px;
}

.output-style-header h3 {
  margin: 0;
}

.output-style-subheader td {
  padding: 5px 20px;
}

.output-style-option td {
  padding: 5px 30px;
}
</style>
