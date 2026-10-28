import { h } from 'vue';
import DesignScope from '@/components/Common/DesignScope.vue';
import { mount } from '@vue/test-utils';
import { NDropdown } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import BaseDropdown from '@/components/Common/BaseDropdown.vue';
import { designTokens } from '@/design/tokens';

describe('BaseDropdown', () => {
  it('preserves menu behavior, trigger slots, and nested local theme overrides', () => {
    const select = vi.fn();
    const wrapper = mount(BaseDropdown, {
      props: {
        trigger: 'click',
        options: [{ label: 'Upload', key: 'upload' }],
        onSelect: select,
        themeOverrides: { peers: { Popover: { padding: '8px' } } },
      },
      slots: { default: '<button>Actions</button>' },
    });
    const dropdown = wrapper.getComponent(NDropdown);
    expect(wrapper.get('button').text()).toBe('Actions');
    expect(dropdown.props('trigger')).toBe('click');
    expect(dropdown.props('themeOverrides')?.peers?.Popover).toEqual(
      expect.objectContaining({
        padding: '8px',
        boxShadow: designTokens.shadow.overlay,
      }),
    );
    dropdown.vm.$emit('select', 'upload');
    expect(select).toHaveBeenCalledWith('upload');
    wrapper.unmount();
  });

  it('themes the teleported action menu and preserves selection', async () => {
    const select = vi.fn();
    const wrapper = mount(DesignScope, {
      attachTo: document.body,
      slots: {
        default: () =>
          h(
            BaseDropdown,
            {
              trigger: 'click',
              options: [{ label: 'Upload', key: 'upload' }],
              renderLabel: () =>
                h('span', { 'data-testid': 'upload-action' }, 'Upload'),
              onSelect: select,
            },
            { default: () => h('button', 'Actions') },
          ),
      },
    });
    await wrapper.get('button').trigger('click');
    const menu = document.querySelector('.base-dropdown') as HTMLElement;
    expect(menu).not.toBeNull();
    expect(menu.style.getPropertyValue('--design-font-ui')).toBe(
      'Tektur, sans-serif',
    );
    const action = menu.querySelector(
      '[data-testid="upload-action"]',
    ) as HTMLElement;
    expect(action.textContent).toContain('Upload');
    action.click();
    expect(select).toHaveBeenCalledWith('upload', expect.anything());
    wrapper.unmount();
  });
});
