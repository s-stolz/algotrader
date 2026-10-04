import { mount } from '@vue/test-utils';
import { NDropdown } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import BaseDropdown from '@/components/Common/BaseDropdown.vue';

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
    expect(dropdown.props('themeOverrides')?.peers?.Popover).toEqual(expect.objectContaining({
      padding: '8px', boxShadow: expect.stringContaining('0 0 0 1px'),
    }));
    dropdown.vm.$emit('select', 'upload');
    expect(select).toHaveBeenCalledWith('upload');
    wrapper.unmount();
  });
});
