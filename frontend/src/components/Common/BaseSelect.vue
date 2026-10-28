<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NSelect, selectProps } from 'naive-ui';
import { designSelectTheme } from '@/design/naiveTheme';
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
          themeOverrides: mergedTheme.value,
        }),
        slots,
      );
  },
});
</script>

<style>
.base-select-menu {
  font-family: var(--design-font-ui);
}
</style>
