<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NPopover, popoverProps } from 'naive-ui';

const themeOverrides: NonNullable<InstanceType<typeof NPopover>['$props']['themeOverrides']> = {
  color: '#171e27',
  textColor: '#dce4ed',
  borderRadius: '8px',
  boxShadow: '0 8px 28px rgba(0, 0, 0, .4)',
  padding: '16px',
};

export default defineComponent({
  name: 'BasePopover',
  inheritAttrs: false,
  props: popoverProps,
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({ ...themeOverrides, ...props.themeOverrides }));
    return () => h(NPopover, mergeProps(attrs, props, {
      class: 'base-popover',
      themeOverrides: mergedTheme.value,
    }), slots);
  },
});
</script>

<style>
.base-popover { border: 1px solid #2b3541; }
.base-popover, .base-popover * { font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
</style>
