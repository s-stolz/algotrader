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
                @update:value="onUpdateStyles(outputKey)"
                v-model:value="styles[outputKey].plotOptions[styleKey]"
              />
            </td>

            <td v-else-if="typeof value === 'number'">
              <n-input-number
                min="1"
                @update:value="onUpdateStyles(outputKey)"
                v-model:value="styles[outputKey].plotOptions[styleKey]"
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
                <n-input-number
                  :min="0"
                  @update:value="onUpdateStyles(outputKey)"
                  v-model:value="styles[outputKey].plotOptions[styleKey][subKey]"
                />
              </td>

              <td v-else-if="typeof subValue === 'string'">
                <n-input
                  @update:value="onUpdateStyles(outputKey)"
                  v-model:value="styles[outputKey].plotOptions[styleKey][subKey]"
                />
              </td>
            </tr>
          </template>
        </template>
      </template>
    </table>
  </n-scrollbar>
</template>

<script>
import { NScrollbar, NH3, NColorPicker, NInput, NInputNumber } from "naive-ui";

export default {
  name: "IndicatorSettingsStyles",

  components: {
    NScrollbar,
    NH3,
    NColorPicker,
    NInput,
    NInputNumber,
  },

  props: {
    indicatorInfo: {
      type: Object,
      required: true,
    },
  },

  emits: ["update-styles"],

  data() {
    return {
      styles: {},
    };
  },

  created() {
    this.initializeStyles();
  },

  methods: {
    onUpdateStyles(outputKey) {
      const styles = this.styles[outputKey]?.plotOptions;
      this.$emit("update-styles", {
        outputKey: outputKey,
        styles: styles,
      });
    },

    initializeStyles() {
      this.styles = {};
      for (const [outputKey, output] of Object.entries(this.indicatorInfo.outputs)) {
        this.styles[outputKey] = {
          plotOptions: { ...(output.plotOptions || {}) },
        };
      }
    },
  },
};
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
