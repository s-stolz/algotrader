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
import { NDatePicker, datePickerProps } from 'naive-ui';
import { designDatePickerTheme } from '@/design/creationControls';
import { installDesignProperties } from '@/design/cssProperties';
import { designTokens } from '@/design/tokens';
import { useDesignScope } from '@/design/scope';

export default defineComponent({
  name: 'BaseDatePicker',
  inheritAttrs: false,
  props: datePickerProps,
  setup(props, { attrs, slots, expose }) {
    const migrated = useDesignScope();
    const picker = shallowRef<InstanceType<typeof NDatePicker>>();
    const portal = shallowRef<HTMLElement>();
    // DatePicker has no panel-props API. Own a body-level teleport target so
    // calendars inherit typography/variables without clipping in scroll areas.
    onMounted(() => {
      if (!migrated || props.to !== undefined) return;
      const target = document.createElement('div');
      target.className = 'base-date-picker-portal';
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
      ...(migrated ? designDatePickerTheme : {}),
      ...props.themeOverrides,
    }));
    return () =>
      h(
        NDatePicker,
        mergeProps(attrs, props, {
          ref: picker,
          class: 'base-date-picker',
          to: props.to ?? portal.value,
          themeOverrides: themeOverrides.value,
        }),
        slots,
      );
  },
});
</script>
