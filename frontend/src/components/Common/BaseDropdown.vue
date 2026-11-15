<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDropdown, dropdownProps } from 'naive-ui';
import { designDropdownTheme } from '@/design/naiveTheme';
import { designCssProperties } from '@/design/cssProperties';

export default defineComponent({
  name: 'BaseDropdown',
  inheritAttrs: false,
  props: dropdownProps,
  setup(props, { attrs, slots }) {
    const theme = designDropdownTheme;
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
          class: 'base-dropdown',
          style: designCssProperties,
          themeOverrides: mergedTheme.value,
        }),
        slots,
      );
  },
});
</script>

<style>
.base-dropdown {
  font-family: var(--design-font-ui);
}
</style>
