import { defineComponent, h, reactive } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { beforeEach, describe, expect, it, vi, onTestFinished } from 'vitest';
import {
  getBacktest,
  listBacktestMembers,
  listBacktestEvents,
} from '@/api/backtesterClient';
import {
  useBacktestInspection,
  type BacktestInspection,
} from '@/components/Backtest/inspection/useBacktestInspection';
import { savedHeatmap } from '../../../views/workspace/heatmap/heatmapFixtures';
import type { Backtest, BacktestRun } from '@/types/backtesterContracts';
const events = vi.hoisted(() => ({ refresh: () => {} }));
vi.mock('@/utils/useBacktestEvents', () => ({
  useBacktestEvents: (refresh: () => void) => {
    events.refresh = refresh;
    return { progress: {} };
  },
}));
vi.mock('@/api/backtesterClient', () => ({
  getBacktest: vi.fn(),
  listBacktestMembers: vi.fn(),
  listBacktestEvents: vi.fn(),
  controlBacktest: vi.fn(),
}));
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function inspection() {
  const props = reactive({ backtestId: 'backtest-1' });
  let state!: BacktestInspection;
  const members = vi.fn();
  const wrapper = mount(
    defineComponent({
      setup() {
        state = useBacktestInspection(props, {
          members,
          cancelled: vi.fn(),
          unavailable: vi.fn(),
        });
        return () => h('div');
      },
    }),
    { global: { plugins: [createPinia()] } },
  );
  onTestFinished(() => wrapper.unmount());
  return { props, state, members };
}
describe('terminal-consistent heatmap member reads', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listBacktestEvents).mockResolvedValue([]);
  });
  it('waits for terminal overview, then refreshed complete members, without polling', async () => {
    const { accepted, runs } = savedHeatmap();
    const overview = deferred<Backtest>();
    const members = deferred<BacktestRun[]>();
    vi.mocked(getBacktest).mockReturnValueOnce(overview.promise);
    vi.mocked(listBacktestMembers).mockReturnValueOnce(members.promise);
    const { state } = inspection();
    await flushPromises();
    expect(listBacktestMembers).not.toHaveBeenCalled();
    overview.resolve(accepted);
    await flushPromises();
    expect(listBacktestMembers).toHaveBeenCalledTimes(1);
    expect(state.terminalSnapshot.value).toBeNull();
    members.resolve(runs);
    await flushPromises();
    expect(state.terminalSnapshot.value?.runs).toEqual(runs);
  });
  it('reconciles terminal events and rejects active member snapshots', async () => {
    const { accepted, runs } = savedHeatmap();
    vi.mocked(getBacktest).mockResolvedValue({
      ...accepted,
      status: 'running',
    });
    vi.mocked(listBacktestMembers).mockResolvedValue(
      runs.map((run) => ({ ...run, status: 'running' })),
    );
    const { state } = inspection();
    await flushPromises();
    expect(state.terminalSnapshot.value).toBeNull();
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    events.refresh();
    await flushPromises();
    expect(state.terminalSnapshot.value).toBeNull();
    expect(state.membersError.value).toContain('not yet terminal');
    vi.mocked(listBacktestMembers).mockResolvedValue(runs);
    events.refresh();
    await flushPromises();
    expect(state.terminalSnapshot.value?.backtest.status).toBe('completed');
  });
  it('retains last-good snapshot on read failure and retries only reads', async () => {
    const { accepted, runs } = savedHeatmap();
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestMembers).mockRejectedValueOnce(new Error('offline'));
    const { state } = inspection();
    await flushPromises();
    expect(state.terminalSnapshot.value).toBeNull();
    expect(state.membersError.value).toBeTruthy();
    vi.mocked(listBacktestMembers).mockResolvedValue(runs);
    await state.refresh();
    const snapshot = state.terminalSnapshot.value;
    vi.mocked(listBacktestMembers).mockRejectedValueOnce(new Error('offline'));
    await state.refresh();
    expect(state.terminalSnapshot.value).toBe(snapshot);
    expect(state.membersError.value).toBeTruthy();
    await state.refresh();
    expect(state.membersError.value).toBeNull();
  });
  it('preserves established membership when a refresh returns an incomplete list', async () => {
    const { accepted, runs } = savedHeatmap();
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestMembers).mockResolvedValue(runs);
    const { state, members } = inspection();
    await flushPromises();
    const snapshot = state.terminalSnapshot.value;
    const calls = members.mock.calls.length;
    vi.mocked(listBacktestMembers).mockResolvedValueOnce(runs.slice(0, 1));
    await state.refresh();
    expect(state.membersError.value).toContain('incomplete');
    expect(state.terminalSnapshot.value).toBe(snapshot);
    expect(state.members.value).toEqual(runs);
    expect(members).toHaveBeenCalledTimes(calls);
  });
  it('invalidates A → B → A member replies and resets heatmap state', async () => {
    const { accepted, runs } = savedHeatmap();
    const old = deferred<BacktestRun[]>();
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestMembers)
      .mockReturnValueOnce(old.promise)
      .mockResolvedValue(runs);
    const { state, props } = inspection();
    await flushPromises();
    props.backtestId = 'B';
    vi.mocked(getBacktest).mockResolvedValue({ ...accepted, backtest_id: 'B' });
    vi.mocked(listBacktestMembers).mockResolvedValue(
      runs.map((run) => ({ ...run, backtest_id: 'B' })),
    );
    await flushPromises();
    expect(state.terminalSnapshot.value?.backtest.backtest_id).toBe('B');
    props.backtestId = 'backtest-1';
    vi.mocked(getBacktest).mockResolvedValue(accepted);
    vi.mocked(listBacktestMembers).mockResolvedValue(runs);
    await flushPromises();
    old.resolve([{ ...runs[0], status: 'running' }]);
    await flushPromises();
    expect(state.terminalSnapshot.value?.runs).toEqual(runs);
    expect(state.members.value).toEqual(runs);
  });
  it('coalesces an event during an active read into a new overview/member pair', async () => {
    const { accepted, runs } = savedHeatmap();
    const old = deferred<BacktestRun[]>();
    vi.mocked(getBacktest)
      .mockResolvedValueOnce({ ...accepted, status: 'running' })
      .mockResolvedValue(accepted);
    vi.mocked(listBacktestMembers)
      .mockReturnValueOnce(old.promise)
      .mockResolvedValue(runs);
    const { state } = inspection();
    await flushPromises();
    events.refresh();
    old.resolve(runs.map((run) => ({ ...run, status: 'running' })));
    await flushPromises();
    expect(getBacktest).toHaveBeenCalledTimes(2);
    expect(state.terminalSnapshot.value?.runs).toEqual(runs);
  });
});
