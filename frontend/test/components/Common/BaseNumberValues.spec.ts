import { nextTick } from 'vue';
import { NSelect } from 'naive-ui';
import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import BaseNumberValues from '@/components/Common/BaseNumberValues.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';

describe('numeric value entry', () => {
  it('shows each created value once after the parent accepts it', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    const wrapper = mount(BaseNumberValues, {
      props: {
        value: [12, 19],
        label: 'Periods',
        'onUpdate:value': (value: number[]) => wrapper.setProps({ value }),
      },
    });
    const select = wrapper.findComponent(NSelect);
    await select.get('input').setValue('20');
    await select.get('input').trigger('keydown', { key: 'Enter' });
    await nextTick();
    await select.get('.n-base-selection').trigger('click');
    await nextTick();
    const menu = (
      select.vm as unknown as {
        treeMate: { treeNodes: Array<{ rawNode: { value: number } }> };
      }
    ).treeMate;
    expect(wrapper.props('value')).toEqual([12, 19, 20]);
    expect(menu.treeNodes.map((node) => node.rawNode.value)).toEqual([
      12, 19, 20,
    ]);
    wrapper.unmount();
    vi.unstubAllGlobals();
  });

  it(
    'rejects invalid and fractional integer entries and emits ' +
      'removable numeric values',
    async () => {
      const wrapper = mount(BaseNumberValues, {
        props: { value: [1, 2], label: 'Periods', integer: true },
      });
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
    },
  );
});
