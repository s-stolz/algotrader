import { mount, flushPromises } from '@vue/test-utils';
import { NColorPicker } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import BaseColorPicker from '@/components/Common/BaseColorPicker.vue';
import DesignScope from '@/components/Common/DesignScope.vue';
import { designTokens } from '@/design/tokens';
import { defineComponent, h } from 'vue';

const Scope = defineComponent({
  setup(_, { slots }) {
    return () => h(DesignScope, {}, slots);
  },
});

describe('BaseColorPicker', () => {
  it('keeps series colors and props, opens by keyboard, and removes its overlay', async () => {
    const update = vi.fn();
    const wrapper = mount(Scope, {
      attachTo: document.body,
      slots: {
        default: () =>
          h(BaseColorPicker, {
            value: '#3366ff',
            'aria-label': 'SMA color',
            'onUpdate:value': update,
          }),
      },
    });
    const control = wrapper.get('[role="button"]');
    const picker = wrapper.getComponent(NColorPicker);
    const host = document.body.querySelector<HTMLElement>(
      '.design-color-picker-overlay',
    )!;
    expect(host.style.fontFamily).toBe('Tektur, sans-serif');
    expect(host.style.getPropertyValue('--design-color-panel')).toBe('#131722');
    expect(picker.props('value')).toBe('#3366ff');
    expect(picker.props('themeOverrides')?.borderRadius).toBe('6px');
    (control.element as HTMLElement).focus();
    await control.trigger('keydown', { key: 'Enter' });
    await flushPromises();
    expect(control.attributes('aria-expanded')).toBe('true');
    expect(host.textContent).toContain('HEXA');
    picker.vm.$emit('update:value', '#ff9900');
    expect(update).toHaveBeenCalledWith('#ff9900');
    await control.trigger('keydown', { key: 'Escape' });
    expect(control.attributes('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(control.element);
    wrapper.unmount();
    expect(document.body.contains(host)).toBe(false);
  });

  it('preserves disabled state and caller theme overrides', async () => {
    const wrapper = mount(BaseColorPicker, {
      props: {
        disabled: true,
        value: '#3366ff',
        themeOverrides: { borderRadius: '9px' },
      },
    });
    const control = wrapper.get('[role="button"]');
    await control.trigger('keydown', { key: ' ' });
    expect(control.attributes('tabindex')).toBe('-1');
    expect(control.attributes('aria-expanded')).toBe('false');
    expect(wrapper.getComponent(NColorPicker).props('themeOverrides')).toEqual({
      color: designTokens.color.panel,
      textColor: designTokens.color.body,
      border: `1px solid ${designTokens.color.border}`,
      borderRadius: '9px',
      boxShadow: designTokens.shadow.overlay,
      panelFontSize: designTokens.text.body,
    });
    wrapper.unmount();
  });
});
