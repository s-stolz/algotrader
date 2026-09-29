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
.base-select-menu {
  border: 1px solid #35414d;
  border-radius: 9px;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
</style>
