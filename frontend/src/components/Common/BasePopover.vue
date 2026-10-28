<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NPopover, popoverProps } from 'naive-ui';

import { designPopoverTheme } from '@/design/naiveTheme';
import { designCssProperties } from '@/design/cssProperties';

export default defineComponent({
  name: 'BasePopover',
  inheritAttrs: false,
  props: popoverProps,
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({
      ...designPopoverTheme,
      ...props.themeOverrides,
    }));
    return () =>
      h(
        NPopover,
        mergeProps(attrs, props, {
          class: 'base-popover',
          style: designCssProperties,
          themeOverrides: mergedTheme.value,
        }),
        slots,
      );
  },
});
</script>

<style>
.base-popover {
  font-family: var(--design-font-ui);
  border: 1px solid var(--design-color-border);
}
</style>
