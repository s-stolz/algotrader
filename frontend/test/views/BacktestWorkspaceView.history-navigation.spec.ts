import {
  setupWorkspaceTests,
  run,
  backtest,
  mountWorkspace,
  pinia,
} from './backtestWorkspaceFixtures';
import { flushPromises, mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import { listBacktests, listBacktestRuns } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';

describe('production Backtest Workspace: history-navigation', () => {
  setupWorkspaceTests();

  it('opens the real creation workflow from the primary header action', async () => {
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    const wrapper = mount(BacktestWorkspaceView, {
      global: {
        plugins: [pinia],
        stubs: {
          BacktestOverview: true,
          EquityReplayCharts: true,
        },
      },
    });
    await flushPromises();
    expect(wrapper.findComponent(BacktestCreationDrawer).exists()).toBe(false);
    await wrapper.get('[data-testid="workspace-create"]').trigger('click');
    await vi.dynamicImportSettled();
    await flushPromises();
    expect(wrapper.getComponent(BacktestCreationDrawer).props('show')).toBe(
      true,
    );
    wrapper.unmount();
  });

  it.each([
    [null, ''],
    ['Selections baseline', 'Selections baseline (copy)'],
  ] as const)(
    'opens Create from this for backtest name %s without changing saved history',
    async (name, proposed) => {
      const saved = { ...backtest('source-backtest', 1), name };
      saved.accepted_definition.shared_request = JSON.parse(
        JSON.stringify(run('settings').request),
      );
      const original = structuredClone(saved);
      vi.mocked(listBacktestRuns).mockResolvedValue([]);
      vi.mocked(listBacktests).mockResolvedValue([saved]);
      const wrapper = mountWorkspace();
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-create-from-source-backtest"]')
        .trigger('click');
      await flushPromises();
      expect(useBacktestWorkspaceStore().reuseSource).toMatchObject({
        kind: 'backtest',
        id: 'source-backtest',
      });
      expect(useBacktestWorkspaceStore().creationDraft?.name).toBe(proposed);
      expect(saved).toEqual(original);
      wrapper.unmount();
    },
  );
});
