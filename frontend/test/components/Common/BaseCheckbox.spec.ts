import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';

describe('BaseCheckbox', () => {
  it('updates checked state through its labeled native input and forwards input attributes', async () => {
    const wrapper = mount(BaseCheckbox, {
      props: { checked: false },
      attrs: { 'data-testid': 'checkbox', name: 'include-null' },
      slots: { default: 'Include null' },
    });
    expect(wrapper.element.tagName).toBe('LABEL');
    expect(wrapper.text()).toBe('Include null');
    const input = wrapper.get<HTMLInputElement>('[data-testid="checkbox"]');
    expect(input.attributes('name')).toBe('include-null');
    await input.setValue(true);
    expect(wrapper.emitted('update:checked')).toEqual([[true]]);
    await wrapper.setProps({ checked: true });
    expect(input.element.checked).toBe(true);
    await input.setValue(false);
    expect(wrapper.emitted('update:checked')).toEqual([[true], [false]]);
    wrapper.unmount();
  });

  it('keeps disabled selection inert and forwards row-interaction guards', () => {
    const onClick = vi.fn((event: MouseEvent) => event.stopPropagation());
    const wrapper = mount(BaseCheckbox, {
      props: { checked: false, disabled: true },
      attrs: { 'aria-label': 'Compare run #1', onClick },
    });
    const input = wrapper.get<HTMLInputElement>('input');
    expect(input.attributes('aria-label')).toBe('Compare run #1');
    input.element.click();
    expect(onClick).not.toHaveBeenCalled();
    expect(wrapper.emitted('update:checked')).toBeUndefined();
    wrapper.unmount();
  });
});
