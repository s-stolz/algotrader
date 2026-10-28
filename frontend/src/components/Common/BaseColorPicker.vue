<script lang="ts">
import { computed, defineComponent, h, ref, Teleport } from 'vue';
import { NColorPicker, colorPickerProps } from 'naive-ui';
import { designCssProperties } from '@/design/cssProperties';
import { designTokens } from '@/design/tokens';

const { color, radius, shadow, text } = designTokens;

export default defineComponent({
  name: 'BaseColorPicker',
  inheritAttrs: false,
  props: colorPickerProps,
  setup(props, { attrs, slots }) {
    const control = ref<HTMLElement | null>(null);
    const isOpen = ref(props.defaultShow ?? false);
    const overlayHost = ref<HTMLElement | null>(null);
    const theme = computed(() => ({
      color: color.panel,
      textColor: color.body,
      border: `1px solid ${color.border}`,
      borderRadius: radius.panel,
      boxShadow: shadow.overlay,
      panelFontSize: text.body,
      ...props.themeOverrides,
    }));

    function updateShow(show: boolean): void {
      isOpen.value = show;
      for (const listener of [
        props.onUpdateShow,
        props['onUpdate:show'],
      ].flat()) {
        listener?.(show);
      }
    }

    function onKeydown(event: KeyboardEvent): void {
      if (props.disabled) return;
      if (event.key === 'Escape') {
        updateShow(false);
        control.value?.focus();
      } else if (
        event.target === event.currentTarget &&
        (event.key === 'Enter' || event.key === ' ')
      ) {
        event.preventDefault();
        updateShow(!(props.show ?? isOpen.value));
      }
    }

    return () =>
      h(
        'div',
        {
          ref: control,
          class: 'design-color-picker',
          tabindex: props.disabled ? -1 : 0,
          role: 'button',
          'aria-label': attrs['aria-label'] ?? 'Choose series color',
          'aria-disabled': props.disabled || undefined,
          'aria-expanded': props.show ?? isOpen.value,
          onKeydown,
        },
        [
          h(
            NColorPicker,
            {
              ...attrs,
              ...props,
              themeOverrides: theme.value,
              show: props.show ?? isOpen.value,
              onUpdateShow: undefined,
              'onUpdate:show': updateShow,
              to: props.to ?? overlayHost.value ?? 'body',
            },
            slots,
          ),
          h(Teleport, { to: 'body' }, [
            h('div', {
              ref: overlayHost,
              class: 'design-color-picker-overlay',
              onKeydown,
              style: {
                ...designCssProperties,
                fontFamily: designTokens.font.ui,
                fontVariantNumeric: 'tabular-nums',
              },
            }),
          ]),
        ],
      );
  },
});
</script>

<style scoped>
.design-color-picker:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: 2px;
  border-radius: var(--design-radius-control);
}

/* Naive shares one radius between its trigger and panel; keep only the
   trigger pill-shaped while the supported theme setting rounds the panel. */
.design-color-picker :deep(.n-color-picker-trigger) {
  border-radius: var(--design-radius-control);
}
</style>
