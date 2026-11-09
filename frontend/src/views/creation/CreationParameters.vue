<template>
  <section
    class="parameters-section"
    aria-label="Strategy parameters"
  >
    <p
      v-if="removedParameters.length"
      class="removed-parameters"
    >
      No longer used: {{ removedParameters.join(', ') }}
    </p>
    <div class="parameters-grid">
      <div
        v-for="parameter in visibleParameters"
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
          <CreationParameterChange :name="parameter.name" />
        </label>
        <BaseSelect
          v-if="!executionSettings"
          size="small"
          class="parameter-mode"
          :aria-label="`${parameter.display_name || parameter.name} mode`"
          :value="parameterInput(parameter).mode"
          :options="parameterModeOptions(parameter)"
          :data-testid="`selections-mode-${parameter.name}`"
          @update:value="changeParameterMode(parameter, $event)"
        />
        <label
          v-if="
            executionSettings || parameterInput(parameter).mode === 'constant'
          "
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
        <template v-else-if="parameterInput(parameter).mode === 'values'">
          <BaseSelect
            v-if="parameter.choices || parameter.type === 'bool'"
            multiple
            max-tag-count="responsive"
            :value="selectedChoiceIndexes(parameter)"
            :options="parameterOptions(parameter)"
            :data-testid="`selections-values-${parameter.name}`"
            @update:value="setParameterChoices(parameter, $event)"
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
                class="string-value-input"
                type="textarea"
                :value="value"
                :aria-label="`${parameter.display_name || parameter.name} value ${index + 1}`"
                :data-testid="`selections-string-${parameter.name}-${index}`"
                @update:value="stringValues(parameter)[index] = $event"
              />
              <n-button
                size="small"
                :data-testid="`selections-remove-${parameter.name}-${index}`"
                @click="stringValues(parameter).splice(index, 1)"
                >Remove value</n-button
              >
            </div>
            <n-button
              size="small"
              :data-testid="`selections-add-${parameter.name}`"
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
            :data-testid="`selections-values-${parameter.name}`"
            @update:value="setNumericValues(parameter, $event)"
            @update:valid="numericEntryValid[parameter.name] = $event"
          />
          <BaseCheckbox
            v-if="
              parameter.nullable &&
              !parameter.choices &&
              parameter.type !== 'bool'
            "
            v-model:checked="parameterInput(parameter).includeNull"
            >Include null</BaseCheckbox
          >
        </template>
        <div
          v-else-if="parameterInput(parameter).mode === 'range'"
          class="range-inputs"
        >
          <label
            >Start<n-input-number
              :input-props="{
                'aria-label': `${parameter.display_name || parameter.name} start`,
              }"
              :data-testid="`selections-start-${parameter.name}`"
              v-model:value="parameterInput(parameter).rangeStart"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
          <label
            >Stop (inclusive)<n-input-number
              :input-props="{
                'aria-label': `${parameter.display_name || parameter.name} stop`,
              }"
              :data-testid="`selections-stop-${parameter.name}`"
              v-model:value="parameterInput(parameter).rangeStop"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
          <label
            >Step<n-input-number
              :input-props="{
                'aria-label': `${parameter.display_name || parameter.name} step`,
              }"
              :data-testid="`selections-step-${parameter.name}`"
              v-model:value="parameterInput(parameter).rangeStep"
              :precision="parameter.type === 'int' ? 0 : undefined"
          /></label>
        </div>
        <small v-if="parameter.description">{{ parameter.description }}</small>
        <small
          v-if="parameterError(parameter.name)"
          role="alert"
          >{{ parameterError(parameter.name) }}</small
        >
      </div>
    </div>
  </section>
</template>
<script setup lang="ts">
const props = defineProps<{ executionSettings?: boolean }>();
import { computed } from 'vue';
import CreationParameterChange from './CreationParameterChange.vue';
import { NButton, NInput, NInputNumber } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import BaseNumberValues from '@/components/Common/BaseNumberValues.vue';
import { parameterModeOptions, parameterOptions } from './creationParameters';
import { useCreation } from './creationContext';
const {
  selectedStrategy,
  parameterChanges,
  parameterIssues,
  draft,
  fieldErrors,
  parameterInput,
  selectValue,
  setChoice,
  setParameter,
  numberValue,
  stringValue,
  stringValues,
  selectedChoiceIndexes,
  setParameterChoices,
  changeParameterMode,
  numericValues,
  setNumericValues,
  numericEntryValid,
} = useCreation();
const visibleParameters = computed(() =>
  (selectedStrategy.value?.parameters ?? []).filter((parameter) => {
    if (!props.executionSettings) return !parameter.purpose;
    const purpose = parameter.purpose;
    if (!purpose) return false;
    const source =
      purpose === 'sizing'
        ? draft.value.execution.sizing
        : draft.value.execution[purpose];
    return !source || source.mode === 'strategy';
  }),
);
function parameterError(name: string): string | undefined {
  return (
    fieldErrors.value[name] ??
    parameterIssues.value.find((issue) => issue.startsWith(`${name}:`))
  );
}
const removedParameters = computed(() =>
  parameterChanges.value
    .filter((item) => item.change === 'Removed')
    .map((item) => item.parameter),
);
</script>
