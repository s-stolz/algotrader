<script lang="ts">
import {
  computed,
  defineComponent,
  h,
  mergeProps,
  onMounted,
  onBeforeUnmount,
  shallowRef,
} from 'vue';
import { NTimePicker, timePickerProps } from 'naive-ui';
import { designTimePickerTheme } from '@/design/creationControls';
import { installDesignProperties } from '@/design/cssProperties';
import { designTokens } from '@/design/tokens';

export default defineComponent({
  name: 'BaseTimePicker',
  inheritAttrs: false,
  props: timePickerProps,
  setup(props, { attrs, slots, expose }) {
    const picker = shallowRef<InstanceType<typeof NTimePicker>>();
    const portal = shallowRef<HTMLElement>();
    // Own the overlay target so times inherit typography and remain visible
    // outside scrolling drawers.
    onMounted(() => {
      if (props.to !== undefined) return;
      const target = document.createElement('div');
      target.className = 'base-time-picker-portal';
      installDesignProperties(target);
      Object.assign(target.style, {
        fontFamily: designTokens.font.ui,
        fontSize: designTokens.text.body,
        color: designTokens.color.body,
      });
      document.body.appendChild(target);
      portal.value = target;
    });
    onBeforeUnmount(() => portal.value?.remove());
    expose({
      focus: () => picker.value?.focus(),
      blur: () => picker.value?.blur(),
    });
    const themeOverrides = computed(() => ({
      ...designTimePickerTheme,
      ...props.themeOverrides,
    }));
    return () =>
      h(
        NTimePicker,
        mergeProps(attrs, props, {
          ref: picker,
          class: 'base-time-picker',
          to: props.to ?? portal.value,
          themeOverrides: themeOverrides.value,
        }),
        slots,
      );
  },
});
</script>
