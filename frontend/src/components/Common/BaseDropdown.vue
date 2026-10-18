<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDropdown, dropdownProps } from 'naive-ui';
import { selectionDropdownTheme } from './selectionTheme';

export default defineComponent({
  name: 'BaseDropdown',
  inheritAttrs: false,
  props: dropdownProps,
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({
      ...selectionDropdownTheme,
      ...props.themeOverrides,
      peers: {
        ...selectionDropdownTheme.peers,
        ...props.themeOverrides?.peers,
        Popover: {
          ...selectionDropdownTheme.peers?.Popover,
          ...props.themeOverrides?.peers?.Popover,
        },
      },
    }));
    return () => h(NDropdown, mergeProps(attrs, props, {
      class: 'base-dropdown',
      themeOverrides: mergedTheme.value,
    }), slots);
  },
});
</script>
