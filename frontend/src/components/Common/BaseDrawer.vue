<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDrawer, drawerProps } from 'naive-ui';
import { designCssProperties } from '@/design/cssProperties';
import { designTokens } from '@/design/tokens';
import { designDrawerTheme } from '@/design/creationControls';

export default defineComponent({
  name: 'BaseDrawer',
  inheritAttrs: false,
  props: drawerProps,
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({
      ...designDrawerTheme,
      ...props.themeOverrides,
    }));

    return () =>
      h(
        NDrawer,
        mergeProps(
          {
            style: {
              ...designCssProperties,
              fontFamily: designTokens.font.ui,
              fontSize: designTokens.text.body,
            },
          },
          attrs,
          props,
          {
            class: 'base-drawer',
            themeOverrides: mergedTheme.value,
          },
        ),
        slots,
      );
  },
});
</script>
