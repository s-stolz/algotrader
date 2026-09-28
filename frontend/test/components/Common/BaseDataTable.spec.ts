import { mount } from '@vue/test-utils';
import { h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import BaseDataTable from '@/components/Common/BaseDataTable.vue';

describe('BaseDataTable', () => {
  it('keeps sorting interactive for column-based tables', async () => {
    const onUpdateSorter = vi.fn();
    const wrapper = mount(BaseDataTable, {
      props: {
        columns: [{ title: 'Price', key: 'price', sorter: 'default' }],
        data: [{ price: 2 }, { price: 1 }],
        rowKey: (row: { price: number }) => row.price,
        onUpdateSorter,
      },
    });

    await wrapper.find('.n-data-table-th').trigger('click');
    await wrapper.find('.n-data-table-th').trigger('click');

    expect(onUpdateSorter).toHaveBeenLastCalledWith(expect.objectContaining({
      columnKey: 'price', order: 'ascend',
    }));
    expect(wrapper.findAll('tbody tr').map((row) => row.text())).toEqual(['1', '2']);
    wrapper.unmount();
  });

  it('renders custom table sections and preserves control interactions', async () => {
    const onClick = vi.fn();
    const wrapper = mount(BaseDataTable, {
      props: { maxHeight: 300, scrollX: 900 },
      attrs: { 'aria-label': 'Settings' },
      slots: {
        default: () => h('tbody', [h('tr', [h('td', { colspan: 2 }, [
          h('button', { onClick }, 'Apply'),
        ])])]),
      },
    });

    expect(wrapper.attributes('aria-label')).toBe('Settings');
    expect(wrapper.find('tbody td').attributes('colspan')).toBe('2');
    await wrapper.find('button').trigger('click');
    expect(onClick).toHaveBeenCalledOnce();
    wrapper.unmount();
  });
});
