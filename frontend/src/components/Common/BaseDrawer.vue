<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDrawer, drawerProps, type DrawerProps } from 'naive-ui';
import { useDesignScope } from '@/design/scope';
import { designCssProperties } from '@/design/cssProperties';
import { designTokens } from '@/design/tokens';
import { designDrawerTheme } from '@/design/creationControls';

const themeOverrides: NonNullable<DrawerProps['themeOverrides']> = {
  color: '#171e27',
  textColor: '#dce4ed',
  titleTextColor: '#dce4ed',
  headerBorderBottom: '1px solid #2b3541',
  footerBorderTop: '1px solid #2b3541',
};

export default defineComponent({
  name: 'BaseDrawer',
  inheritAttrs: false,
  props: drawerProps,
  setup(props, { attrs, slots }) {
    const migrated = useDesignScope();
    const mergedTheme = computed(() => ({
      ...(migrated ? designDrawerTheme : themeOverrides),
      ...props.themeOverrides,
    }));

    return () =>
      h(
        NDrawer,
        mergeProps(
          {
            style: migrated
              ? {
                  ...designCssProperties,
                  fontFamily: designTokens.font.ui,
                  fontSize: designTokens.text.body,
                }
              : undefined,
          },
          attrs,
          props,
          {
            class: ['base-drawer', { 'base-drawer-design': migrated }],
            themeOverrides: mergedTheme.value,
          },
        ),
        slots,
      );
  },
});
</script>

<style>
.base-drawer:not(.base-drawer-design),
.base-drawer:not(.base-drawer-design) * {
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
}
</style>
