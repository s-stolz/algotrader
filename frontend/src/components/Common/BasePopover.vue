<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NPopover, popoverProps } from 'naive-ui';

import { selectionPopoverTheme } from './selectionTheme';

export default defineComponent({
  name: 'BasePopover',
  inheritAttrs: false,
  props: popoverProps,
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({ ...selectionPopoverTheme, ...props.themeOverrides }));
    return () => h(NPopover, mergeProps(attrs, props, {
      class: 'base-popover',
      themeOverrides: mergedTheme.value,
    }), slots);
  },
});
</script>

<style>
.base-popover { border: 1px solid #2b3541; }
.base-popover, .base-popover * { font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
</style>
