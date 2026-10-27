<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue';
import { NButton } from 'naive-ui';
import BasePopover from './BasePopover.vue';
import { designTokens } from '@/design/tokens';

const props = withDefaults(
  defineProps<{
    value: string;
    label: string;
    groups: readonly {
      label: string;
      options: readonly { label: string; value: string; disabled?: boolean }[];
    }[];
    disabled?: boolean;
    triggerWidth?: string;
  }>(),
  { disabled: false, triggerWidth: undefined },
);
const emit = defineEmits<{ 'update:value': [value: string] }>();
const show = ref(false);
const trigger = ref<InstanceType<typeof NButton> | null>(null);
const listbox = ref<HTMLElement | null>(null);
const listboxId = useId();
const keyboardOpen = ref(false);
const options = computed(() => props.groups.flatMap((group) => group.options));
const enabledOptions = computed(() =>
  options.value.filter((option) => !option.disabled),
);
const currentLabel = computed(
  () =>
    options.value.find((option) => option.value === props.value)?.label ??
    props.value,
);
const activeValue = ref(props.value);
const { color, space, radius, control, text } = designTokens;
const buttonTheme = {
  color: 'transparent',
  colorHover: color.hover,
  colorPressed: color.selected,
  colorFocus: 'transparent',
  textColor: color.body,
  textColorHover: color.body,
  textColorPressed: color.body,
  textColorFocus: color.body,
  border: '1px solid transparent',
  borderHover: `1px solid ${color.border}`,
  borderPressed: `1px solid ${color.interactive}`,
  borderFocus: `1px solid ${color.interactive}`,
  rippleColor: color.interactive,
  borderRadiusSmall: radius.control,
  heightSmall: control.small,
  fontSizeSmall: text.body,
  paddingSmall: '0',
};
const selectedButtonTheme = {
  ...buttonTheme,
  color: color.selected,
  colorHover: color.selectedHover,
  colorPressed: color.selected,
  colorFocus: color.selected,
  textColor: color.interactive,
  textColorHover: color.interactive,
  textColorPressed: color.interactive,
  textColorFocus: color.interactive,
  border: `1px solid ${color.interactive}`,
  borderHover: `1px solid ${color.interactive}`,
};

function close(restoreFocus = false): void {
  show.value = false;
  keyboardOpen.value = false;
  if (restoreFocus) trigger.value?.$el.focus();
}
function updateShow(next: boolean): void {
  // Mouse movement must not dismiss a picker being navigated with the keyboard.
  if (!next && keyboardOpen.value) return;
  if (props.disabled || !enabledOptions.value.length) return;
  show.value = next;
  if (next)
    activeValue.value =
      enabledOptions.value.find((option) => option.value === props.value)
        ?.value ?? enabledOptions.value[0].value;
}
async function openWithKeyboard(): Promise<void> {
  if (props.disabled || !enabledOptions.value.length) return;
  updateShow(true);
  keyboardOpen.value = true;
  await nextTick();
  focusActiveOption();
}
function focusActiveOption(): void {
  const buttons =
    listbox.value?.querySelectorAll<HTMLElement>('[role="option"]');
  buttons?.forEach((button) => {
    if (button.dataset.value === activeValue.value) button.focus();
  });
}
function select(value: string): void {
  emit('update:value', value);
  close(true);
}
function navigate(event: KeyboardEvent): void {
  const values = enabledOptions.value.map((option) => option.value);
  if (!values.length) return;
  let index = values.indexOf(activeValue.value);
  switch (event.key) {
    case 'ArrowDown':
    case 'ArrowRight':
      index = (index + 1) % values.length;
      break;
    case 'ArrowUp':
    case 'ArrowLeft':
      index = (index - 1 + values.length) % values.length;
      break;
    case 'Home':
      index = 0;
      break;
    case 'End':
      index = values.length - 1;
      break;
    default:
      return;
  }
  event.preventDefault();
  keyboardOpen.value = true;
  activeValue.value = values[index];
  focusActiveOption();
}
function leaveFocus(event: FocusEvent): void {
  const target = event.relatedTarget as Node | null;
  if (listbox.value?.contains(target) || trigger.value?.$el.contains(target))
    return;
  close();
}
</script>

<template>
  <BasePopover
    :show="show"
    trigger="hover"
    placement="bottom-start"
    :show-arrow="false"
    :delay="80"
    :duration="150"
    :theme-overrides="{ padding: space.md }"
    @update:show="updateShow"
    @clickoutside="close()"
  >
    <template #trigger>
      <n-button
        ref="trigger"
        round
        :style="{ width: triggerWidth }"
        :disabled="disabled || !enabledOptions.length"
        :aria-label="label"
        aria-haspopup="listbox"
        :aria-expanded="show"
        :aria-controls="show ? listboxId : undefined"
        @click="openWithKeyboard"
        @keydown.down.prevent="openWithKeyboard"
        @keydown.up.prevent="openWithKeyboard"
        @keydown.esc.stop.prevent="close(true)"
        @focusout="leaveFocus"
        >{{ currentLabel }}</n-button
      >
    </template>
    <div
      :id="listboxId"
      ref="listbox"
      class="base-grouped-select"
      role="listbox"
      :aria-label="label"
      @keydown="navigate"
      @keydown.esc.stop.prevent="close(true)"
      @focusout="leaveFocus"
    >
      <section
        v-for="group in groups.filter((entry) => entry.options.length)"
        :key="group.label"
        class="selection-group"
        role="group"
        :aria-label="group.label"
      >
        <h3 aria-hidden="true">{{ group.label }}</h3>
        <div class="selection-options">
          <n-button
            v-for="option in group.options"
            :key="option.value"
            size="small"
            role="option"
            :aria-selected="value === option.value"
            :disabled="option.disabled"
            :data-value="option.value"
            :tabindex="activeValue === option.value ? 0 : -1"
            :theme-overrides="
              value === option.value ? selectedButtonTheme : buttonTheme
            "
            class="selection-option"
            @click="select(option.value)"
            >{{ option.label }}</n-button
          >
        </div>
      </section>
    </div>
  </BasePopover>
</template>

<style scoped>
.base-grouped-select {
  width: 224px;
  max-width: calc(100vw - 56px);
  display: flex;
  flex-direction: column;
  gap: var(--design-space-md);
}
.selection-group h3 {
  margin: 0 0 var(--design-space-sm);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
  font-weight: 500;
  line-height: 14px;
}
.selection-group + .selection-group {
  border-top: 1px solid var(--design-color-border);
  padding-top: var(--design-space-md);
}
.selection-options {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--design-space-xs);
}
.selection-option:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: 2px;
}
</style>
