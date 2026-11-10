import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import { NPagination, NSwitch } from 'naive-ui';
import ExecutionLogPanel from '@/components/Backtest/execution-log/ExecutionLogPanel.vue';
import { useExecutionLogStore } from '@/stores/executionLogStore';
import { fetchExecutionLog } from '@/api/executionLogClient';
import { backtestRun } from '../../../api/backtesterClient.fixtures';
import { logPage, orderItem } from '../../../executionLogFixtures';
vi.mock('@/api/executionLogClient', () => ({ fetchExecutionLog: vi.fn() }));
beforeEach(() => {
  setActivePinia(createPinia());
  vi.mocked(fetchExecutionLog).mockReset();
});
describe('execution log panel', () => {
  it('requests server pages and resets the page when unexecuted orders are enabled', async () => {
    vi.mocked(fetchExecutionLog).mockImplementation(
      async (id, page, include) => {
        const result = logPage(id, page);
        if (include) result.items[0] = orderItem();
        return result;
      },
    );
    const store = useExecutionLogStore();
    store.selectRun(backtestRun());
    const wrapper = mount(ExecutionLogPanel);
    await flushPromises();
    expect(wrapper.findAll('tbody')).toHaveLength(10);
    expect(wrapper.findAll('tbody tr')).toHaveLength(20);
    expect(wrapper.find('td[data-interior-cell]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Fees');
    wrapper.findComponent(NPagination).vm.$emit('update:page', 2);
    await flushPromises();
    expect(store.page).toBe(2);
    wrapper.findComponent(NSwitch).vm.$emit('update:value', true);
    await flushPromises();
    expect(store.page).toBe(1);
    expect(wrapper.text()).toContain('Not executed');
    expect(wrapper.text()).toContain('Intended buy');
    expect(wrapper.text()).not.toContain('private-order-id');
    expect(wrapper.find('.unexecuted-order').exists()).toBe(true);
    expect(wrapper.findAll('tbody')).toHaveLength(10);
    expect(wrapper.findAll('tbody tr')).toHaveLength(19);
    wrapper.unmount();
  });
  it('shows retryable failures and a distinct empty state', async () => {
    vi.mocked(fetchExecutionLog)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(logPage('run-123', 1, 0));
    useExecutionLogStore().selectRun(backtestRun());
    const wrapper = mount(ExecutionLogPanel);
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('offline');
    await wrapper.get('button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('No closed trades');
    expect(wrapper.findComponent(NPagination).exists()).toBe(false);
    wrapper.unmount();
  });
});
