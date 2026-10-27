<template>
  <section
    class="parameters-section"
    aria-labelledby="parameters-heading"
  >
    <h3 id="parameters-heading">Strategy parameters</h3>
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
          <small
            v-if="
              parameter.minimum !== undefined || parameter.maximum !== undefined
            "
            class="parameter-constraints"
          >
            <span v-if="parameter.minimum !== undefined">
              {{ parameter.exclusive_minimum ? '>' : '≥' }}
              {{ parameter.minimum }}
            </span>
            <span v-if="parameter.maximum !== undefined">
              {{ parameter.exclusive_maximum ? '<' : '≤' }}
              {{ parameter.maximum }}
            </span>
          </small>
        </label>
        <BaseSelect
          v-if="isSweep"
          size="small"
          class="parameter-mode"
          :aria-label="`${parameter.display_name || parameter.name} mode`"
          :value="sweepParameter(parameter).mode"
          :options="parameterModeOptions(parameter)"
          :data-testid="`sweep-mode-${parameter.name}`"
          @update:value="sweepParameter(parameter).mode = $event"
        />
        <BaseSelect
          v-if="
            (!isSweep || sweepParameter(parameter).mode === 'constant') &&
            (parameter.choices || parameter.type === 'bool')
          "
          :id="`parameter-${parameter.name}`"
          :value="selectValue(parameter)"
          :options="parameterOptions(parameter)"
          :data-testid="`creation-param-${parameter.name}`"
          @update:value="setChoice(parameter, $event)"
        />
        <n-input-number
          v-else-if="
            (!isSweep || sweepParameter(parameter).mode === 'constant') &&
            (parameter.type === 'int' || parameter.type === 'float')
          "
          :id="`parameter-${parameter.name}`"
          :value="numberValue(parameter.name)"
          :min="parameter.minimum"
          :max="parameter.maximum"
          :precision="parameter.type === 'int' ? 0 : undefined"
          :data-testid="`creation-param-${parameter.name}`"
          @update:value="setParameter(parameter.name, $event)"
        />
        <n-input
          v-else-if="!isSweep || sweepParameter(parameter).mode === 'constant'"
          :id="`parameter-${parameter.name}`"
          :value="stringValue(parameter.name)"
          :data-testid="`creation-param-${parameter.name}`"
          @update:value="setParameter(parameter.name, $event)"
        />
        <template v-else-if="sweepParameter(parameter).mode === 'values'">
          <BaseSelect
            v-if="parameter.choices || parameter.type === 'bool'"
            multiple
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
          <n-input
            v-else
            type="textarea"
            :value="sweepParameter(parameter).valuesText"
            placeholder="One numeric value per line"
            :data-testid="`sweep-values-${parameter.name}`"
            @update:value="sweepParameter(parameter).valuesText = $event"
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
              v-model:value="sweepParameter(parameter).rangeStart"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
          <label
            >Stop<n-input-number
              v-model:value="sweepParameter(parameter).rangeStop"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
          <label
            >Step<n-input-number
              v-model:value="sweepParameter(parameter).rangeStep"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
        </div>
        <n-button
          v-if="
            (!isSweep || sweepParameter(parameter).mode === 'constant') &&
            parameter.nullable &&
            !parameter.choices &&
            parameter.type !== 'bool'
          "
          size="tiny"
          class="null-button"
          @click="setParameter(parameter.name, null)"
          >Set null</n-button
        >
        <small
          v-if="
            parameter.nullable &&
            draft.strategy.parameters[parameter.name] === null
          "
        >
          Null selected
        </small>
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
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import { NButton, NInput, NInputNumber } from 'naive-ui';
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
} = useCreation();
</script>
