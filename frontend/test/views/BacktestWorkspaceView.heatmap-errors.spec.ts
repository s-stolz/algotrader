import {
  setupWorkspaceTests,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { savedHeatmap } from './workspace/heatmap/heatmapFixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  getBacktest,
  getBacktestRun,
  listBacktests,
  listBacktestMembers,
} from '@/api/backtesterClient';
import ParameterHeatmap from '@/views/workspace/heatmap/ParameterHeatmap.vue';
import BacktestOverview from '@/components/Backtest/BacktestOverview.vue';
import type { BacktestRun } from '@/types/backtesterContracts';
function seed() {
  const { accepted, runs } = savedHeatmap();
  vi.mocked(listBacktests).mockResolvedValue([accepted]);
  vi.mocked(getBacktest).mockResolvedValue(accepted);
  vi.mocked(listBacktestMembers).mockResolvedValue(runs);
  vi.mocked(getBacktestRun).mockImplementation(async (id) =>
    runs.find((run) => run.run_id === id)!,
  );
  return { accepted, runs };
}
async function open() {
  const wrapper = mountWorkspace(true);
  await flushPromises();
  await wrapper
    .get('[data-testid="workspace-backtest-backtest-1"]')
    .trigger('click');
  await flushPromises();
  return wrapper;
}
const cases: [string, (runs: BacktestRun[]) => BacktestRun[], string][] = [
  [
    'identity',
    (runs) => [{ ...runs[0], backtest_id: 'wrong' }, ...runs.slice(1)],
    'Saved Run identities or ordinals are invalid.',
  ],
  [
    'ordinal',
    (runs) => [{ ...runs[0], run_ordinal: 99 }, ...runs.slice(1)],
    'Saved Run identities or ordinals are invalid.',
  ],
  [
    'incomplete membership',
    (runs) => runs.slice(0, 1),
    'The saved member list is incomplete.',
  ],
];
describe('visible heatmap membership errors', () => {
  setupWorkspaceTests();
  it.each(cases)(
    'explains initial %s errors without an invalid grid',
    async (_, invalid, message) => {
      const { runs } = seed();
      vi.mocked(listBacktestMembers).mockResolvedValue(invalid(runs));
      const wrapper = await open();
      expect(wrapper.text()).toContain(message);
      expect(wrapper.findComponent(ParameterHeatmap).exists()).toBe(false);
      expect(
        wrapper.find('[data-testid="workspace-member-member-0"]').exists(),
      ).toBe(true);
      await wrapper
        .get('[data-testid="workspace-member-member-0"]')
        .trigger('click');
      await flushPromises();
      expect(getBacktestRun).toHaveBeenCalledWith('member-0', false);
    },
  );
  it.each(cases)(
    'explains refresh %s errors while retaining the valid snapshot',
    async (_, invalid, message) => {
      const { runs } = seed();
      const wrapper = await open();
      const snapshot = wrapper.getComponent(ParameterHeatmap).props('saved');
      await wrapper
        .get('[data-testid="comparison-select-member-1"]')
        .setValue(true);
      vi.mocked(listBacktestMembers).mockResolvedValue(invalid(runs));
      await wrapper.getComponent(BacktestOverview).vm.refresh();
      await flushPromises();
      expect(wrapper.text()).toContain(message);
      expect(wrapper.getComponent(ParameterHeatmap).props('saved')).toBe(
        snapshot,
      );
      expect(
        wrapper.get<HTMLInputElement>(
          '[data-testid="comparison-select-member-1"]',
        ).element.checked,
      ).toBe(true);
      expect(
        wrapper.find('[data-testid="workspace-member-member-2"]').exists(),
      ).toBe(true);
    },
  );
});
