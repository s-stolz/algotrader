import { mount } from '@vue/test-utils';
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
        options: [{ label: 'EURUSD', value: 'EURUSD' }, { label: 'GBPUSD', value: 'GBPUSD' }],
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
    expect(select.props('menuProps')?.class).toEqual(['base-select-menu', 'custom-menu']);
    expect(select.props('themeOverrides')).toEqual(expect.objectContaining({
      peers: expect.objectContaining({
        InternalSelection: expect.objectContaining({ borderRadius: '12px', color: '#171e27' }),
        InternalSelectMenu: expect.objectContaining({ optionTextColorActive: '#63d2b0' }),
      }),
    }));
    select.vm.$emit('update:value', ['GBPUSD']);
    expect(onUpdate).toHaveBeenCalledWith(['GBPUSD']);
    wrapper.unmount();
  });
});
