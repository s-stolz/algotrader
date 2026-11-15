import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ExecutionLogTable from '@/components/Backtest/execution-log/ExecutionLogTable.vue';
import { tradeItem, orderItem } from '../../../executionLogFixtures';

describe('execution prices and quantities', () => {
  it('preserves distinct fractional prices and small executed quantities', () => {
    const item = tradeItem(0);
    if (item.kind !== 'trade') throw new Error('Expected trade fixture');
    Object.assign(item.trade, {
      entry_price: 1.08456,
      exit_price: 1.08459,
      quantity: 0.0001,
    });
    const wrapper = mount(ExecutionLogTable, {
      props: { items: [item], currency: 'EUR' },
    });
    const rows = wrapper.findAll('tbody tr');
    expect(rows[0].findAll('td')[3].text()).toBe('1.08459');
    expect(rows[0].findAll('td')[4].text()).toBe('0.0001');
    expect(rows[1].findAll('td')[2].text()).toBe('1.08456');
    wrapper.unmount();
  });
});

it('emits each trade endpoint and provides no jump for unexecuted orders', async () => {
  const item = tradeItem(0);
  if (item.kind !== 'trade') throw new Error('Expected trade');
  const wrapper = mount(ExecutionLogTable, {
    props: { items: [item, orderItem()], currency: null },
  });
  await wrapper.get('[aria-label="Go to entry"]').trigger('click');
  await wrapper.get('[aria-label="Go to exit"]').trigger('click');
  expect(wrapper.emitted('jump')).toEqual([
    [item.trade.entry_timestamp_ms],
    [item.trade.exit_timestamp_ms],
  ]);
  expect(wrapper.findAll('button')).toHaveLength(2);
  wrapper.unmount();
});
