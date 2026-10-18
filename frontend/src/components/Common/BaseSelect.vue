<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NSelect, selectProps } from 'naive-ui';
import { baseSelectTheme } from './baseSelectTheme';

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
    const menuProps = computed(() => ({
      ...props.menuProps,
      class: ['base-select-menu', props.menuProps?.class],
    }));
    return () => h(NSelect, mergeProps(attrs, props, {
      class: 'base-select',
      menuProps: menuProps.value,
      themeOverrides: mergedTheme.value,
    }), slots);
  },
});
</script>

<style>
.base-select-menu, .base-select-menu * { font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.base-select-menu {
  border-radius: 6px;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
/* Also covers Naive UI's pagination size selector, which shares baseSelectTheme. */
.n-select .n-base-selection:not(.n-base-selection--disabled):is(:hover, .n-base-selection--focus) .n-base-selection-input {
  color: var(--selection-accent);
}
</style>
