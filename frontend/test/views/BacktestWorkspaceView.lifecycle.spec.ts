import { setupWorkspaceTests, run, pinia } from './backtestWorkspaceFixtures';
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h, KeepAlive } from 'vue';
import { NPagination } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import { getBacktestRun, listBacktestRuns } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { BacktestRun } from '@/types/backtesterContracts';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';

describe('production Backtest Workspace: kept-alive state ownership', () => {
  setupWorkspaceTests();

  it('retains history and comparison state while rejecting an inactive read', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const saved = Array.from({ length: 20 }, (_, index) =>
      run(`retained-${index}`),
    );
    let finishInactiveRead!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestRuns)
      .mockResolvedValueOnce(saved)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishInactiveRead = resolve;
          }),
      )
      .mockResolvedValue(saved);
    vi.mocked(getBacktestRun).mockImplementation(
      async (id) => saved.find((entry) => entry.run_id === id)!,
    );
    const host = mount(
      defineComponent({
        props: { active: Boolean },
        setup: (props) => () =>
          h(KeepAlive, null, {
            default: () => (props.active ? h(BacktestWorkspaceView) : null),
          }),
      }),
      {
        props: { active: true },
        global: {
          plugins: [pinia],
          stubs: { EquityReplayCharts: true, BacktestBatches: true },
        },
      },
    );
    await flushPromises();
    const workspace = () => host.getComponent(BacktestWorkspaceView);
    await workspace()
      .get('[data-testid="workspace-search"] input')
      .setValue('retained');
    workspace().findAllComponents(NPagination)[0]!.vm.$emit('update:page', 2);
    await flushPromises();
    await workspace()
      .get('[data-testid="workspace-run-retained-16"]')
      .trigger('click');
    await flushPromises();
    await workspace()
      .get('[data-testid="workspace-history-return"]')
      .trigger('click');
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(listBacktestRuns).toHaveBeenCalledTimes(2);

    // jsdom omits the browser scroll method used by Naive reactivation.
    for (const scrollbar of host.findAll('.n-scrollbar-container')) {
      Object.assign(scrollbar.element, { scrollTo: vi.fn() });
    }
    await host.setProps({ active: false });
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(listBacktestRuns).toHaveBeenCalledTimes(2);
    await host.setProps({ active: true });
    await flushPromises();
    expect(listBacktestRuns).toHaveBeenCalledTimes(3);
    finishInactiveRead([run('superseded')]);
    await flushPromises();

    expect(
      workspace().get<HTMLInputElement>(
        '[data-testid="workspace-search"] input',
      ).element.value,
    ).toBe('retained');
    expect(workspace().findAllComponents(NPagination)[0]!.props('page')).toBe(
      2,
    );
    expect(
      workspace().find('[data-testid="workspace-run-superseded"]').exists(),
    ).toBe(false);
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('retained-16');
    expect(
      workspace().get<HTMLInputElement>(
        '[data-testid="comparison-select-retained-16"]',
      ).element.checked,
    ).toBe(true);
    host.unmount();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(listBacktestRuns).toHaveBeenCalledTimes(3);
  });
});
