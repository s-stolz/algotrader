import { mount } from '@vue/test-utils';
import { ref, nextTick } from 'vue';
import { it, expect, vi } from 'vitest';
import MonthlyResults from '@/views/workspace/results/MonthlyResults.vue';
import { summarizeTrades } from '@/views/workspace/results/runResults';
import type { BacktestWorkspace } from '@/views/workspace/useBacktestWorkspace';
import { resultRun, resultTrade } from './resultFixtures';
it('stacks selected runs and both units in read-only year rows', async () => {
  const first = resultRun('first');
  const second = { ...resultRun('second'), run_ordinal: 1 };
  const selection = ref(['first', 'second']);
  const inspection = {
    currentRows: ref([first, second]),
    selectedComparisonIds: selection,
    tradeResults: {
      states: ref({
        first: {
          status: 'ready',
          result: summarizeTrades([resultTrade(100)], Infinity),
        },
        second: {
          status: 'ready',
          result: summarizeTrades([resultTrade(-50)], 0),
        },
      }),
      retry: vi.fn(),
    },
  } as unknown as BacktestWorkspace['inspection'];
  const wrapper = mount(MonthlyResults, { props: { inspection } });
  expect(wrapper.findAll('tbody tr')).toHaveLength(1);
  const january = wrapper.find('tbody td');
  expect(january.text()).toContain('+100.00');
  expect(january.text()).toContain('1.00%');
  expect(january.text()).toContain('-50.00');
  expect(january.findAll('.run-result')).toHaveLength(2);
  await january.trigger('click');
  expect(wrapper.find('button').exists()).toBe(false);
  selection.value = ['second'];
  await nextTick();
  expect(wrapper.findAll('tbody td').at(-1)!.text()).toContain('-50.00');
  expect(wrapper.find('tbody td').findAll('.run-result')).toHaveLength(1);
  selection.value = [];
  await nextTick();
  expect(wrapper.find('table').exists()).toBe(false);
});
