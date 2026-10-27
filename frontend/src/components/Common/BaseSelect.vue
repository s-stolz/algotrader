<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NSelect, selectProps } from 'naive-ui';
import { baseSelectTheme } from './baseSelectTheme';
import { designSelectTheme } from '@/design/naiveTheme';
import { designCssProperties } from '@/design/cssProperties';
import { useDesignScope } from '@/design/scope';

export default defineComponent({
  name: 'BaseSelect',
  inheritAttrs: false,
  props: selectProps,
  setup(props, { attrs, slots }) {
    const usesDesign = useDesignScope();
    const theme = usesDesign ? designSelectTheme : baseSelectTheme;
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
      class: [
        usesDesign ? 'base-select-menu--design' : 'base-select-menu',
        props.menuProps?.class,
      ],
      style: usesDesign
        ? [designCssProperties, props.menuProps?.style]
        : props.menuProps?.style,
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
.base-select-menu,
.base-select-menu * {
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
}
.base-select-menu {
  border-radius: 6px;
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
}
.base-select-menu--design,
.base-select-menu--design * {
  font-family: var(--design-font-ui);
}
/* Naive's input text has no supported hover/focus text theme role.
   Keep this compatibility override here with its owning control.
   Also covers Naive UI's pagination size selector, which shares baseSelectTheme. */
.n-select
  .n-base-selection:not(.n-base-selection--disabled):is(
    :hover,
    .n-base-selection--focus
  )
  .n-base-selection-input {
  color: var(--selection-accent);
}
</style>
