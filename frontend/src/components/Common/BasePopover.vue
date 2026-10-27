<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NPopover, popoverProps } from 'naive-ui';

import { selectionPopoverTheme } from './selectionTheme';
import { designPopoverTheme } from '@/design/naiveTheme';
import { designCssProperties } from '@/design/cssProperties';
import { useDesignScope } from '@/design/scope';

export default defineComponent({
  name: 'BasePopover',
  inheritAttrs: false,
  props: popoverProps,
  setup(props, { attrs, slots }) {
    const usesDesign = useDesignScope();
    const mergedTheme = computed(() => ({
      ...(usesDesign ? designPopoverTheme : selectionPopoverTheme),
      ...props.themeOverrides,
    }));
    return () =>
      h(
        NPopover,
        mergeProps(attrs, props, {
          class: ['base-popover', { 'base-popover--design': usesDesign }],
          style: usesDesign ? designCssProperties : undefined,
          themeOverrides: mergedTheme.value,
        }),
        slots,
      );
  },
});
</script>

<style>
.base-popover {
  border: 1px solid var(--surface-border);
}
.base-popover:not(.base-popover--design),
.base-popover:not(.base-popover--design) * {
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
}
.base-popover--design {
  border-color: var(--design-color-border);
}
.base-popover--design,
.base-popover--design * {
  font-family: var(--design-font-ui);
}
</style>
