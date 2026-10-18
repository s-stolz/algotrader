<script setup lang="ts">
import { NCheckbox, type CheckboxProps } from 'naive-ui';

const themeOverrides: NonNullable<CheckboxProps['themeOverrides']> = {
  color: '#171e27', colorChecked: '#63d2b0', colorDisabled: '#202833',
  colorDisabledChecked: '#202833', checkMarkColor: '#10231d',
  border: '1px solid #8190a0', borderChecked: '1px solid #63d2b0',
  borderFocus: '1px solid #63d2b0', borderDisabled: '1px solid #35414d',
  borderDisabledChecked: '1px solid #35414d', borderRadius: '4px',
  textColor: '#dce4ed', textColorDisabled: '#8190a0',
};
defineOptions({ inheritAttrs: false });
withDefaults(defineProps<{ checked?: boolean; disabled?: boolean; indeterminate?: boolean }>(), {
  checked: false,
  disabled: false,
  indeterminate: undefined,
});
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
    :theme-overrides="themeOverrides"
    @update:checked="emit('update:checked', $event)"
  ><slot /></n-checkbox>
  <component v-else :is="$slots.default ? 'label' : 'span'" class="base-checkbox" :class="{ 'base-checkbox-disabled': disabled }">
    <input
      v-bind="$attrs"
      class="base-checkbox-input"
      type="checkbox"
      role="checkbox"
      :checked="checked"
      :disabled="disabled"
      @change="updateChecked"
    >
    <span v-if="$slots.default" class="base-checkbox-label"><slot /></span>
  </component>
</template>

<style scoped>
.base-checkbox { display: inline-flex; align-items: center; gap: 8px; vertical-align: middle; color: #dce4ed; cursor: pointer; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 14px; line-height: 1.5; }
.base-checkbox-disabled { color: #8190a0; cursor: not-allowed; }
.base-checkbox-label { min-width: 0; overflow-wrap: anywhere; }
.base-checkbox-input {
  flex-shrink: 0;
  appearance: none;
  display: inline-grid;
  place-content: center;
  width: 16px;
  height: 16px;
  margin: 0;
  vertical-align: middle;
  border: 1px solid #8190a0;
  border-radius: 4px;
  background: #171e27;
  cursor: pointer;
}
.base-checkbox-input:not(:disabled):hover { border-color: #63d2b0; }
.base-checkbox-input:checked { background: #63d2b0; border-color: #63d2b0; }
.base-checkbox-input:checked::after {
  content: '';
  width: 4px;
  height: 8px;
  margin-top: -2px;
  border: solid #10231d;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}
.base-checkbox-input:disabled {
  background: #202833;
  border-color: #35414d;
  cursor: not-allowed;
}
.base-checkbox:deep(.n-checkbox-box) { width: 16px; height: 16px; }
.base-checkbox:deep(.n-checkbox-box--focus) { outline: 2px solid #63d2b0; outline-offset: 3px; }
.base-checkbox-input:focus-visible { outline: 2px solid #63d2b0; outline-offset: 3px; }
</style>
