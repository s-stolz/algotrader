<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDrawer, drawerProps, type DrawerProps } from 'naive-ui';

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
    const mergedTheme = computed(() => ({ ...themeOverrides, ...props.themeOverrides }));

    return () => h(NDrawer, mergeProps(attrs, props, {
      class: 'base-drawer',
      themeOverrides: mergedTheme.value,
    }), slots);
  },
});
</script>

<style>
.base-drawer, .base-drawer * {
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
</style>
