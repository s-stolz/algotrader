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
  fetchBacktestClosedTrades,
} from '@/api/backtesterClient';
import ParameterHeatmap from '@/views/workspace/heatmap/ParameterHeatmap.vue';
import { NPagination } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
vi.mock('@/views/workspace/heatmap/HeatmapPlot.vue', () => ({
  default: {
    name: 'HeatmapPlot',
    props: ['cells', 'selectedIds', 'bounds', 'pending'],
    template: '<div data-testid="heatmap-plot" />',
  },
}));
describe('production heatmap comparison integration', () => {
  setupWorkspaceTests();
  it('synchronizes comparison toggles independently of trade reads', async () => {
    const { accepted, runs } = savedHeatmap();
    vi.mocked(listBacktests).mockResolvedValue([accepted]);
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestMembers).mockResolvedValue(runs);
    vi.mocked(getBacktestRun).mockImplementation(async (id) =>
      runs.find((run) => run.run_id === id)!,
    );
    vi.mocked(fetchBacktestClosedTrades).mockImplementation(
      () => new Promise(() => {}),
    );
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-backtest-1"]')
      .trigger('click');
    await flushPromises();
    const heatmap = wrapper.getComponent(ParameterHeatmap);
    const selects = heatmap.findAllComponents(BaseSelect);
    selects[0].vm.$emit('update:value', 'parameter:fast');
    selects[1].vm.$emit('update:value', 'parameter:slow');
    selects[2].vm.$emit('update:value', 'return');
    await flushPromises();
    const plot = () => heatmap.getComponent({ name: 'HeatmapPlot' });
    expect(plot().props('bounds')).toEqual([-10.12345, 1000]);
    expect(plot().props('pending')).toBe(false);
    const tradeReads = vi.mocked(fetchBacktestClosedTrades).mock.calls.length;
    for (const run of [runs[0], runs[1], runs[0]]) {
      plot().vm.$emit('inspect', run);
      await flushPromises();
    }
    expect(plot().props('selectedIds')).toEqual([runs[1].run_id]);
    expect(
      wrapper.get<HTMLInputElement>(
        '[data-testid="comparison-select-member-1"]',
      ).element.checked,
    ).toBe(true);
    await wrapper
      .get('[data-testid="comparison-select-member-2"]')
      .setValue(true);
    await flushPromises();
    expect(plot().props('selectedIds')).toEqual([
      runs[1].run_id,
      runs[2].run_id,
    ]);
    expect(selects[0].props('value')).toBe('parameter:fast');
    expect(selects[2].props('value')).toBe('return');
    for (const run of [runs[1], runs[2]]) {
      plot().vm.$emit('inspect', run);
      await flushPromises();
    }
    expect(plot().props('selectedIds')).toEqual([]);
    expect(fetchBacktestClosedTrades).toHaveBeenCalledTimes(tradeReads);
  });
  it('retains off-page comparisons through swaps and slice changes', async () => {
    const { accepted, runs } = savedHeatmap();
    const members = Array.from({ length: 25 }, (_, index) => ({
      ...structuredClone(runs[0]),
      run_id: `wide-${index}`,
      run_ordinal: index,
    }));
    members.forEach((run, index) => {
      run.request.strategy.parameters.fast = index;
    });
    const saved = accepted.accepted_definition.normalized_selections;
    saved.parameters.fast.values = members.map((_, index) => index);
    accepted.raw_count = 100;
    accepted.member_count = accepted.total_count = accepted.settled_count = 25;
    accepted.outcome_counts.succeeded = 25;
    vi.mocked(listBacktests).mockResolvedValue([accepted]);
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(async (id) =>
      members.find((run) => run.run_id === id)!,
    );
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-backtest-backtest-1"]')
      .trigger('click');
    await flushPromises();
    const heatmap = wrapper.getComponent(ParameterHeatmap);
    const selects = heatmap.findAllComponents(BaseSelect);
    selects[0].vm.$emit('update:value', 'parameter:fast');
    selects[1].vm.$emit('update:value', 'parameter:slow');
    selects[2].vm.$emit('update:value', 'return');
    await flushPromises();
    const plot = () => heatmap.getComponent({ name: 'HeatmapPlot' });
    expect(
      wrapper.find('[data-testid="comparison-select-wide-24"]').exists(),
    ).toBe(false);
    plot().vm.$emit('inspect', members[24]);
    await flushPromises();
    expect(plot().props('selectedIds')).toEqual(['wide-24']);
    await heatmap.get('[aria-label="Swap axes"]').trigger('click');
    expect(plot().props('selectedIds')).toEqual(['wide-24']);
    heatmap
      .getComponent({ name: 'FixedInputsPopover' })
      .vm.$emit('change', 'parameter:choice', '"two"');
    await flushPromises();
    expect(
      plot()
        .props('cells')
        .every((cell: { run?: unknown }) => !cell.run),
    ).toBe(true);
    expect(plot().props('selectedIds')).toEqual(['wide-24']);
    wrapper.findAllComponents(NPagination).at(-1)!.vm.$emit('update:page', 2);
    await flushPromises();
    expect(
      wrapper.get<HTMLInputElement>('[data-testid="comparison-select-wide-24"]')
        .element.checked,
    ).toBe(true);
  });
});
