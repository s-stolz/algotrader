<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NPopover, NSelect, selectProps } from 'naive-ui';
import { designTokens } from '@/design/tokens';
import { designSelectTheme, designPopoverTheme } from '@/design/naiveTheme';
import { designCssProperties } from '@/design/cssProperties';

export default defineComponent({
  name: 'BaseSelect',
  inheritAttrs: false,
  props: selectProps,
  setup(props, { attrs, slots }) {
    const theme = designSelectTheme;
    const mergedTheme = computed(() => ({
      ...theme,
      ...props.themeOverrides,
      peers: {
        ...theme.peers,
        ...props.themeOverrides?.peers,
        InternalSelection: {
          ...theme.peers?.InternalSelection,
          ...props.themeOverrides?.peers?.InternalSelection,
        },
        InternalSelectMenu: {
          ...theme.peers?.InternalSelectMenu,
          ...props.themeOverrides?.peers?.InternalSelectMenu,
        },
      },
    }));
    const ellipsisTagPopoverProps = computed(() => {
      const overrides = props.ellipsisTagPopoverProps as
        InstanceType<typeof NPopover>['$props'] | undefined;
      return {
        placement: 'bottom-start' as const,
        overlap: false,
        showArrow: false,
        ...overrides,
        class: ['base-select-overflow', overrides?.class],
        style: [designCssProperties, overrides?.style],
        themeOverrides: {
          ...designPopoverTheme,
          padding: designTokens.space.sm,
          boxShadow: `0 0 0 1px ${designTokens.color.border}, ${designTokens.shadow.overlay}`,
          ...overrides?.themeOverrides,
        },
      };
    });
    const menuProps = computed(() => ({
      ...props.menuProps,
      class: ['base-select-menu', props.menuProps?.class],
      style: [designCssProperties, props.menuProps?.style],
    }));
    return () =>
      h(
        NSelect,
        mergeProps(attrs, props, {
          class: 'base-select',
          menuProps: menuProps.value,
          ellipsisTagPopoverProps: ellipsisTagPopoverProps.value,
          themeOverrides: mergedTheme.value,
        }),
        slots,
      );
  },
});
</script>

<style>
.base-select {
  min-width: 0;
}
.base-select-menu,
.base-select-overflow {
  font-family: var(--design-font-ui);
}
</style>
