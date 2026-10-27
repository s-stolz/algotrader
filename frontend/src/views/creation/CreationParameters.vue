<template>
  <section
    class="parameters-section"
    aria-label="Strategy parameters"
  >
    <div class="parameters-grid">
      <div
        v-for="parameter in selectedStrategy?.parameters ?? []"
        :key="parameter.name"
        class="parameter-field"
      >
        <label
          class="parameter-label"
          :for="`parameter-${parameter.name}`"
        >
          <span
            >{{ parameter.display_name || parameter.name
            }}<span v-if="parameter.required"> *</span></span
          >
        </label>
        <BaseSelect
          v-if="isSweep"
          size="small"
          class="parameter-mode"
          :aria-label="`${parameter.display_name || parameter.name} mode`"
          :value="sweepParameter(parameter).mode"
          :options="parameterModeOptions(parameter)"
          :data-testid="`sweep-mode-${parameter.name}`"
          @update:value="changeParameterMode(parameter, $event)"
        />
        <label
          v-if="!isSweep || sweepParameter(parameter).mode === 'constant'"
          class="parameter-value"
          >Value
          <BaseSelect
            v-if="parameter.choices || parameter.type === 'bool'"
            :id="`parameter-${parameter.name}`"
            :input-props="{
              'aria-label': parameter.display_name || parameter.name,
            }"
            :value="selectValue(parameter)"
            :options="parameterOptions(parameter)"
            :data-testid="`creation-param-${parameter.name}`"
            @update:value="setChoice(parameter, $event)"
          />
          <n-input-number
            v-else-if="parameter.type === 'int' || parameter.type === 'float'"
            :id="`parameter-${parameter.name}`"
            :input-props="{
              'aria-label': parameter.display_name || parameter.name,
            }"
            :value="numberValue(parameter.name)"
            :clearable="parameter.nullable"
            :placeholder="
              draft.strategy.parameters[parameter.name] === null
                ? 'Null'
                : 'Enter value'
            "
            :min="parameter.minimum"
            :max="parameter.maximum"
            :precision="parameter.type === 'int' ? 0 : undefined"
            :data-testid="`creation-param-${parameter.name}`"
            @update:value="setParameter(parameter.name, $event)"
          />
          <n-input
            v-else
            :id="`parameter-${parameter.name}`"
            :input-props="{
              'aria-label': parameter.display_name || parameter.name,
            }"
            :value="stringValue(parameter.name)"
            :placeholder="
              draft.strategy.parameters[parameter.name] === null
                ? 'Null'
                : 'Enter value'
            "
            :data-testid="`creation-param-${parameter.name}`"
            @update:value="setParameter(parameter.name, $event)"
          >
            <template
              v-if="
                parameter.nullable &&
                draft.strategy.parameters[parameter.name] !== null
              "
              #suffix
            >
              <n-button
                text
                :aria-label="`Clear ${parameter.display_name || parameter.name} to null`"
                title="Clear to null"
                @click="setParameter(parameter.name, null)"
                >×</n-button
              >
            </template>
          </n-input>
        </label>
        <template v-else-if="sweepParameter(parameter).mode === 'values'">
          <BaseSelect
            v-if="parameter.choices || parameter.type === 'bool'"
            multiple
            max-tag-count="responsive"
            :value="selectedChoiceIndexes(parameter)"
            :options="parameterOptions(parameter)"
            :data-testid="`sweep-values-${parameter.name}`"
            @update:value="setSweepChoices(parameter, $event)"
          />
          <div
            v-else-if="parameter.type === 'str'"
            class="string-values"
          >
            <div
              v-for="(value, index) in stringValues(parameter)"
              :key="index"
              class="string-value"
            >
              <n-input
                type="textarea"
                :value="value"
                :aria-label="`${parameter.display_name || parameter.name} value ${index + 1}`"
                :data-testid="`sweep-string-${parameter.name}-${index}`"
                @update:value="stringValues(parameter)[index] = $event"
              />
              <n-button
                size="small"
                :data-testid="`sweep-remove-${parameter.name}-${index}`"
                @click="stringValues(parameter).splice(index, 1)"
                >Remove value</n-button
              >
            </div>
            <n-button
              size="small"
              :data-testid="`sweep-add-${parameter.name}`"
              @click="stringValues(parameter).push('')"
              >Add string value</n-button
            >
            <small
              >Each field is one exact string. An empty field is an empty
              string.</small
            >
          </div>
          <BaseNumberValues
            v-else
            :value="numericValues(parameter)"
            :label="`${parameter.display_name || parameter.name} values`"
            :integer="parameter.type === 'int'"
            :data-testid="`sweep-values-${parameter.name}`"
            @update:value="setNumericValues(parameter, $event)"
            @update:valid="numericEntryValid[parameter.name] = $event"
          />
          <BaseCheckbox
            v-if="
              parameter.nullable &&
              !parameter.choices &&
              parameter.type !== 'bool'
            "
            v-model:checked="sweepParameter(parameter).includeNull"
            >Include null</BaseCheckbox
          >
        </template>
        <div
          v-else-if="sweepParameter(parameter).mode === 'range'"
          class="range-inputs"
        >
          <label
            >Start<n-input-number
              :input-props="{
                'aria-label': `${parameter.display_name || parameter.name} start`,
              }"
              :data-testid="`sweep-start-${parameter.name}`"
              v-model:value="sweepParameter(parameter).rangeStart"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
          <label
            >Stop (inclusive)<n-input-number
              :input-props="{
                'aria-label': `${parameter.display_name || parameter.name} stop`,
              }"
              :data-testid="`sweep-stop-${parameter.name}`"
              v-model:value="sweepParameter(parameter).rangeStop"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
          <label
            >Step<n-input-number
              :input-props="{
                'aria-label': `${parameter.display_name || parameter.name} step`,
              }"
              :data-testid="`sweep-step-${parameter.name}`"
              v-model:value="sweepParameter(parameter).rangeStep"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
        </div>
        <small v-if="parameter.description">{{ parameter.description }}</small>
        <small
          v-if="fieldErrors[parameter.name]"
          role="alert"
          >{{ fieldErrors[parameter.name] }}</small
        >
      </div>
    </div>
  </section>
</template>
<script setup lang="ts">
import { NButton, NInput, NInputNumber } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import BaseNumberValues from '@/components/Common/BaseNumberValues.vue';
import { parameterModeOptions, parameterOptions } from './creationParameters';
import { useCreation } from './creationContext';
const {
  selectedStrategy,
  isSweep,
  draft,
  fieldErrors,
  sweepParameter,
  selectValue,
  setChoice,
  setParameter,
  numberValue,
  stringValue,
  stringValues,
  selectedChoiceIndexes,
  setSweepChoices,
  changeParameterMode,
  numericValues,
  setNumericValues,
  numericEntryValid,
} = useCreation();
</script>
