import { flushPromises, mount } from '@vue/test-utils';
import { NDatePicker } from 'naive-ui';
import { h } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import BaseDatePicker from '@/components/Common/BaseDatePicker.vue';
import DesignScope from '@/components/Common/DesignScope.vue';
import { designTokens } from '@/design/tokens';

describe('BaseDatePicker', () => {
  it('themes its calendar outside a scrolling ancestor and cleans up', async () => {
    const onUpdateShow = vi.fn();
    const wrapper = mount(DesignScope, {
      attachTo: document.body,
      slots: {
        default: () =>
          h(BaseDatePicker, {
            show: true,
            value: Date.UTC(2026, 9, 15),
            inputReadonly: true,
            onUpdateShow,
          }),
      },
    });
    await flushPromises();
    const portal = document.querySelector<HTMLElement>(
      '.base-date-picker-portal',
    )!;
    expect(portal.parentElement).toBe(document.body);
    expect(portal.textContent).toContain('2026');
    expect(portal.style.fontFamily).toBe(designTokens.font.ui);
    expect(portal.style.getPropertyValue('--design-color-interactive')).toBe(
      designTokens.color.interactive,
    );
    const input = wrapper.get('input');
    await input.trigger('keydown', { key: 'Escape' });
    expect(onUpdateShow).toHaveBeenCalledWith(false);
    wrapper.unmount();
    expect(document.querySelector('.base-date-picker-portal')).toBeNull();
  });

  it('preserves disabled inputs, focus, events, and caller theme overrides', async () => {
    const onFocus = vi.fn();
    const onUpdateFormattedValue = vi.fn();
    const wrapper = mount(BaseDatePicker, {
      props: {
        disabled: true,
        formattedValue: '2026-10-15',
        valueFormat: 'yyyy-MM-dd',
        onFocus,
        onUpdateFormattedValue,
        themeOverrides: { panelBorderRadius: '9px' },
      },
      attrs: { 'aria-label': 'Start date' },
    });
    expect(wrapper.get('input').attributes('disabled')).toBeDefined();
    expect(wrapper.findComponent(NDatePicker).props('themeOverrides')).toEqual({
      panelBorderRadius: '9px',
    });
    expect(document.querySelector('.base-date-picker-portal')).toBeNull();
    await wrapper.setProps({ disabled: false });
    await wrapper.get('input').trigger('focus');
    expect(onFocus).toHaveBeenCalled();
    await wrapper.get('input').setValue('2026-10-16');
    await wrapper.get('input').trigger('change');
    expect(onUpdateFormattedValue).toHaveBeenCalledWith(
      '2026-10-16',
      expect.anything(),
    );
    wrapper.unmount();
  });
});
