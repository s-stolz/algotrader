<script setup lang="ts">
import { NCheckbox } from 'naive-ui';
import { designCheckboxTheme } from '@/design/creationControls';

defineOptions({ inheritAttrs: false });
withDefaults(
  defineProps<{
    checked?: boolean;
    disabled?: boolean;
    indeterminate?: boolean;
  }>(),
  {
    checked: false,
    disabled: false,
    indeterminate: undefined,
  },
);
const emit = defineEmits<{ 'update:checked': [checked: boolean] }>();
function updateChecked(event: Event): void {
  emit('update:checked', (event.target as HTMLInputElement).checked);
}
</script>

<template>
  <n-checkbox
    v-if="indeterminate !== undefined"
    v-bind="$attrs"
    class="base-checkbox"
    :checked="checked"
    :disabled="disabled"
    :indeterminate="indeterminate"
    :theme-overrides="designCheckboxTheme"
    @update:checked="emit('update:checked', $event)"
    ><slot
  /></n-checkbox>
  <component
    v-else
    :is="$slots.default ? 'label' : 'span'"
    class="base-checkbox"
    :class="{
      'base-checkbox-disabled': disabled,
    }"
  >
    <input
      v-bind="$attrs"
      class="base-checkbox-input"
      type="checkbox"
      role="checkbox"
      :checked="checked"
      :disabled="disabled"
      @change="updateChecked"
    />
    <span
      v-if="$slots.default"
      class="base-checkbox-label"
      ><slot
    /></span>
  </component>
</template>

<style scoped>
.base-checkbox {
  display: inline-flex;
  align-items: center;
  gap: var(--design-space-sm);
  vertical-align: middle;
  color: var(--design-color-body);
  cursor: pointer;
  font-family: var(--design-font-ui);
  font-size: var(--design-text-body);
  line-height: 1.5;
}
.base-checkbox-disabled {
  color: var(--design-color-disabled-text);
  cursor: not-allowed;
}
.base-checkbox-label {
  min-width: 0;
  overflow-wrap: anywhere;
}
.base-checkbox-input {
  flex-shrink: 0;
  appearance: none;
  display: inline-grid;
  place-content: center;
  width: 16px;
  height: 16px;
  margin: 0;
  vertical-align: middle;
  border: 1px solid var(--design-color-control-border);
  border-radius: var(--design-space-xs);
  background: var(--design-color-inset);
  cursor: pointer;
}
.base-checkbox-input:not(:disabled):hover {
  border-color: var(--design-color-interactive);
}
.base-checkbox-input:checked {
  background: var(--design-color-interactive);
  border-color: var(--design-color-interactive);
}
.base-checkbox-input:checked::after {
  content: '';
  width: 4px;
  height: 8px;
  margin-top: -2px;
  border: solid var(--design-color-on-interactive);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}
.base-checkbox-input:disabled {
  background: var(--design-color-disabled);
  border-color: var(--design-color-disabled-border);
  cursor: not-allowed;
}
.base-checkbox-input:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: 3px;
}
</style>
