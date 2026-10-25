import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import BaseNumberValues from '@/components/Common/BaseNumberValues.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';

describe('numeric value entry', () => {
  it('rejects invalid and fractional integer entries and emits removable numeric values', async () => {
    const wrapper = mount(BaseNumberValues, { props: { value: [1, 2], label: 'Periods', integer: true } });
    const select = wrapper.findComponent(BaseSelect);
    for (const input of ['oops', '1.5', 'Infinity']) {
      select.vm.$emit('search', input);
      await wrapper.vm.$nextTick();
      expect(wrapper.find('[role="alert"]').exists()).toBe(true);
      select.vm.$emit('update:value', [1, 2, input]);
      expect(wrapper.emitted('update:value')).toBeUndefined();
    }
    select.vm.$emit('search', '3');
    await wrapper.vm.$nextTick();
    select.vm.$emit('update:value', [1, 2, 3]);
    expect(wrapper.emitted('update:value')?.[0]).toEqual([[1, 2, 3]]);
    select.vm.$emit('update:value', [2]);
    expect(wrapper.emitted('update:value')?.[1]).toEqual([[2]]);
    select.vm.$emit('search', 'unfinished');
    await wrapper.vm.$nextTick();
    expect(wrapper.emitted('update:valid')?.at(-1)).toEqual([false]);
    wrapper.unmount();
    expect(wrapper.emitted('update:valid')?.at(-1)).toEqual([true]);
  });
});
