<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NPopover, NSelect, selectProps } from 'naive-ui';
import { baseSelectTheme } from './baseSelectTheme';
import { selectionColors, selectionPopoverTheme } from './selectionTheme';

export default defineComponent({
  name: 'BaseSelect',
  inheritAttrs: false,
  props: selectProps,
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({
      ...baseSelectTheme,
      ...props.themeOverrides,
      peers: {
        ...baseSelectTheme.peers,
        ...props.themeOverrides?.peers,
        InternalSelection: {
          ...baseSelectTheme.peers?.InternalSelection,
          ...props.themeOverrides?.peers?.InternalSelection,
        },
        InternalSelectMenu: {
          ...baseSelectTheme.peers?.InternalSelectMenu,
          ...props.themeOverrides?.peers?.InternalSelectMenu,
        },
      },
    }));
    const ellipsisTagPopoverProps = computed(() => {
      const overrides = props.ellipsisTagPopoverProps as InstanceType<typeof NPopover>['$props'] | undefined;
      return {
        placement: 'bottom-start' as const,
        overlap: false,
        showArrow: false,
        ...overrides,
        class: ['base-select-overflow', overrides?.class],
        themeOverrides: {
          ...selectionPopoverTheme,
          padding: '8px',
          boxShadow: `0 0 0 1px ${selectionColors.border}, 0 8px 24px rgba(0, 0, 0, .4)`,
          ...overrides?.themeOverrides,
        },
      };
    });
    const menuProps = computed(() => ({
      ...props.menuProps,
      class: ['base-select-menu', props.menuProps?.class],
    }));
    return () => h(NSelect, mergeProps(attrs, props, {
      class: 'base-select',
      menuProps: menuProps.value,
      ellipsisTagPopoverProps: ellipsisTagPopoverProps.value,
      themeOverrides: mergedTheme.value,
    }), slots);
  },
});
</script>

<style>
.base-select { min-width: 0; }
.base-select-menu, .base-select-menu *, .base-select-overflow, .base-select-overflow * { font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.base-select-menu {
  border-radius: 6px;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
/* Also covers Naive UI's pagination size selector, which shares baseSelectTheme. */
.n-select .n-base-selection:not(.n-base-selection--disabled):is(:hover, .n-base-selection--focus) .n-base-selection-input {
  color: var(--selection-accent);
}
</style>
