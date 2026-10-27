<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDropdown, dropdownProps } from 'naive-ui';
import { selectionDropdownTheme } from './selectionTheme';
import { designDropdownTheme } from '@/design/naiveTheme';
import { designCssProperties } from '@/design/cssProperties';
import { useDesignScope } from '@/design/scope';

export default defineComponent({
  name: 'BaseDropdown',
  inheritAttrs: false,
  props: dropdownProps,
  setup(props, { attrs, slots }) {
    const usesDesign = useDesignScope();
    const theme = usesDesign ? designDropdownTheme : selectionDropdownTheme;
    const mergedTheme = computed(() => ({
      ...theme,
      ...props.themeOverrides,
      peers: {
        ...theme.peers,
        ...props.themeOverrides?.peers,
        Popover: {
          ...theme.peers?.Popover,
          ...props.themeOverrides?.peers?.Popover,
        },
      },
    }));
    return () =>
      h(
        NDropdown,
        mergeProps(attrs, props, {
          class: ['base-dropdown', { 'base-dropdown--design': usesDesign }],
          style: usesDesign ? designCssProperties : undefined,
          themeOverrides: mergedTheme.value,
        }),
        slots,
      );
  },
});
</script>

<style>
.base-dropdown--design,
.base-dropdown--design * {
  font-family: var(--design-font-ui);
}
</style>
