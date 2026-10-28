import {
  setupWorkspaceTests,
  run,
  batch,
  mountWorkspace,
  fill,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestEquityCurve,
  fetchBacktestFills,
  getBacktestBatch,
  getBacktestRun,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

describe('production Backtest Workspace: polling-inspection', () => {
  setupWorkspaceTests();
  it('keeps settled replay series loaded across unchanged batch polling', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const members = [0, 1].map((ordinal) =>
      run(`member-${ordinal}`, { batch_id: 'stable', member_ordinal: ordinal }),
    );
    const accepted = batch('stable', 2);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue(members);
    vi.mocked(getBacktestRun).mockImplementation(
      async (id) => members.find((run) => run.run_id === id)!,
    );
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'exact',
      reason: null,
      source_point_count: 1,
      returned_point_count: 1,
      sampled: false,
      equity_curve: [
        { timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 },
      ],
    });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-batch-stable"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .find('[data-testid="comparison-select-member-0"]')
      .setValue(true);
    await wrapper
      .find('[data-testid="comparison-select-member-1"]')
      .setValue(true);
    await flushPromises();
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'member-0',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(listBacktestBatchMembers).toHaveBeenCalledTimes(2);
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(2);
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'member-0',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'member-1',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    wrapper.unmount();
  });

  it('keeps selected content steady while background detail reads are pending', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const saved = run('steady');
    vi.mocked(listBacktestRuns).mockResolvedValue([saved]);
    vi.mocked(getBacktestRun).mockResolvedValue(saved);
    const wrapper = mountWorkspace();
    await flushPromises();
    await wrapper.find('[data-testid="workspace-run-steady"]').trigger('click');
    await flushPromises();
    const selectedTable = wrapper
      .get('[data-testid="workspace-current-backtest"]')
      .text();
    vi.mocked(getBacktestRun).mockImplementation(() => new Promise(() => {}));
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(
      wrapper.get('[data-testid="workspace-current-backtest"]').text(),
    ).toBe(selectedTable);
    const reads = vi.mocked(getBacktestRun).mock.calls.length;
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(getBacktestRun).toHaveBeenCalledTimes(reads);
    wrapper.unmount();
  });

  it('keeps completed curves visible while another batch member settles', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const success = run('settled', { batch_id: 'active', member_ordinal: 0 });
    const pending = run('pending', {
      batch_id: 'active',
      member_ordinal: 1,
      status: 'running',
      metrics: null,
    });
    const accepted = batch('active', 2);
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([success, pending]);
    vi.mocked(getBacktestRun).mockResolvedValue(success);
    vi.mocked(fetchBacktestEquityCurve).mockResolvedValue({
      availability: 'exact',
      reason: null,
      source_point_count: 1,
      returned_point_count: 1,
      sampled: false,
      equity_curve: [
        { timestamp_ms: 1_714_521_600_000, equity: 10050, drawdown_pct: -1 },
      ],
    });
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-batch-active"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .find('[data-testid="comparison-select-settled"]')
      .setValue(true);
    await flushPromises();
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([
      success,
      { ...pending, status: 'failed' },
    ]);
    vi.mocked(fetchBacktestEquityCurve).mockImplementation(
      () => new Promise(() => {}),
    );
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(
      wrapper.findComponent({ name: 'EquityReplayCharts' }).props('series'),
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: 'settled',
          points: [
            {
              timestamp_ms: 1_714_521_600_000,
              equity: 10050,
              drawdown_pct: -1,
            },
          ],
        }),
      ]),
    );
    expect(fetchBacktestEquityCurve).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it('preserves member logs and standalone log filters across history polls', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const saved = run('standalone');
    const member = run('member', { batch_id: 'logs', member_ordinal: 0 });
    const accepted = batch('logs', 1);
    vi.mocked(listBacktestRuns).mockImplementation(async () => [
      structuredClone(saved),
    ]);
    vi.mocked(listBacktestBatches).mockResolvedValue([accepted]);
    vi.mocked(getBacktestBatch).mockResolvedValue(accepted);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([]);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([member]);
    vi.mocked(getBacktestRun).mockImplementation(async (id) =>
      id === saved.run_id ? saved : member,
    );
    vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'sell')]);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-run-standalone"]')
      .trigger('click');
    await flushPromises();
    await wrapper
      .find('[data-testid="workspace-log-standalone"]')
      .trigger('click');
    await flushPromises();
    document.body
      .querySelector<HTMLButtonElement>('[data-testid="execution-fills-tab"]')!
      .click();
    await wrapper.vm.$nextTick();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="execution-fills-table"]'),
    ).not.toBeNull();
    expect(fetchBacktestFills).toHaveBeenCalledTimes(1);
    document.body
      .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
      .click();
    await wrapper.vm.$nextTick();
    await wrapper.find('[data-testid="workspace-batch-logs"]').trigger('click');
    await flushPromises();
    await wrapper.find('[data-testid="workspace-log-member"]').trigger('click');
    await flushPromises();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(document.body.textContent).toContain('Execution log · Run #1');
    wrapper.unmount();
  });
});
