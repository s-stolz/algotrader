import { mount } from '@vue/test-utils';
import { h } from 'vue';
import DesignScope from '@/components/Common/DesignScope.vue';
import { NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';

import BaseSelect from '@/components/Common/BaseSelect.vue';

describe('BaseSelect', () => {
  it('forwards select behavior and gives the control and menu the shared design', async () => {
    const onUpdate = vi.fn();
    const wrapper = mount(BaseSelect, {
      attrs: { 'aria-label': 'Choose Markets', 'data-testid': 'markets' },
      props: {
        value: ['EURUSD'],
        multiple: true,
        options: [
          { label: 'EURUSD', value: 'EURUSD' },
          { label: 'GBPUSD', value: 'GBPUSD' },
        ],
        menuProps: { class: 'custom-menu' },
        themeOverrides: {
          peers: { InternalSelection: { borderRadius: '12px' } },
        },
        'onUpdate:value': onUpdate,
      },
    });
    const select = wrapper.getComponent(NSelect);
    expect(select.props('value')).toEqual(['EURUSD']);
    expect(select.props('multiple')).toBe(true);
    expect(select.attributes('aria-label')).toBe('Choose Markets');
    expect(select.attributes('data-testid')).toBe('markets');
    expect(select.classes()).toContain('base-select');
    expect(select.props('menuProps')?.class).toEqual([
      'base-select-menu',
      'custom-menu',
    ]);
    expect(select.props('themeOverrides')).toEqual(
      expect.objectContaining({
        peers: expect.objectContaining({
          InternalSelection: expect.objectContaining({
            borderRadius: '12px',
            color: '#131722',
          }),
          InternalSelectMenu: expect.objectContaining({
            optionTextColorActive: '#dce4ed',
          }),
        }),
      }),
    );
    select.vm.$emit('update:value', ['GBPUSD']);
    expect(onUpdate).toHaveBeenCalledWith(['GBPUSD']);
    wrapper.unmount();
  });

  it('keeps keyboard selection and scoped typography in the teleported menu', async () => {
    const onUpdate = vi.fn();
    // jsdom does not implement native element scrolling used by menu navigation.
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: vi.fn(),
    });
    const wrapper = mount(DesignScope, {
      attachTo: document.body,
      slots: {
        default: () =>
          h(BaseSelect, {
            value: null,
            virtualScroll: false,
            options: [
              { label: 'Unavailable', value: 'disabled', disabled: true },
              { label: 'Forex', value: 'Forex' },
            ],
            'aria-label': 'Market Type',
            'onUpdate:value': onUpdate,
          }),
      },
    });
    const combobox = wrapper.get('[tabindex="0"]');
    await combobox.trigger('keydown', { key: 'ArrowDown', code: 'ArrowDown' });
    const menu = document.querySelector(
      '.base-select-menu--design',
    ) as HTMLElement;
    expect(menu).not.toBeNull();
    expect(menu.style.getPropertyValue('--design-font-ui')).toBe(
      'Tektur, sans-serif',
    );
    expect(menu.textContent).toContain('Forex');
    await combobox.trigger('keydown', { key: 'Enter', code: 'Enter' });
    expect(onUpdate).toHaveBeenCalledWith('Forex', expect.anything());
    wrapper.unmount();
    Reflect.deleteProperty(HTMLElement.prototype, 'scrollTo');
  });
});
