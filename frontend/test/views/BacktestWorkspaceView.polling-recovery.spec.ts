import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import { getBacktestRun, listBacktestRuns } from '@/api/backtesterClient';

import type { BacktestRun } from '@/types/backtesterContracts';

describe('production Backtest Workspace: polling-recovery', () => {
  setupWorkspaceTests();
  it('reports an unavailable initial history read without calling it empty', async () => {
    vi.mocked(listBacktestRuns).mockRejectedValue(
      new Error('Service unavailable'),
    );
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.text()).not.toContain('No saved Backtest Runs.');
    wrapper.unmount();
  });

  it('shows reconciled failure and preserves queued work on Workspace refresh', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    const queued = run('waiting', { status: 'queued', metrics: null });
    const interrupted = run('active', {
      status: 'failed',
      metrics: null,
      error_code: 'worker_interrupted',
      error_message: 'Backtest worker was interrupted before completion',
    });
    vi.mocked(listBacktestRuns)
      .mockResolvedValueOnce([
        run('active', { status: 'running', metrics: null }),
        queued,
      ])
      .mockResolvedValueOnce([interrupted, queued]);
    vi.mocked(getBacktestRun).mockResolvedValue(interrupted);
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-run-active"]').text(),
    ).toContain('running');

    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(
      wrapper.find('[data-testid="workspace-run-active"]').text(),
    ).toContain('failed');
    expect(
      wrapper.find('[data-testid="workspace-run-waiting"]').text(),
    ).toContain('queued');
    await wrapper.find('[data-testid="workspace-run-active"]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain(
      'Backtest worker was interrupted before completion',
    );

    wrapper.unmount();
    vi.advanceTimersByTime(5000);
    await flushPromises();
    expect(listBacktestRuns).toHaveBeenCalledTimes(2);
  });

  it('accepts a history response that takes longer than the polling interval', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let resolveRead!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestRuns).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRead = resolve;
        }),
    );
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.text()).toContain('Loading saved runs');

    vi.advanceTimersByTime(6000);
    expect(listBacktestRuns).toHaveBeenCalledOnce();
    resolveRead([run('slow-success')]);
    await flushPromises();

    expect(
      wrapper.find('[data-testid="workspace-run-slow-success"]').exists(),
    ).toBe(true);
    expect(wrapper.text()).not.toContain('Loading saved runs');
    wrapper.unmount();
  });

  it('shows a slow read error after a polling interval instead of loading forever', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let rejectRead!: (error: Error) => void;
    vi.mocked(listBacktestRuns).mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          rejectRead = reject;
        }),
    );
    const wrapper = mountWorkspace();
    await flushPromises();

    vi.advanceTimersByTime(6000);
    expect(listBacktestRuns).toHaveBeenCalledOnce();
    rejectRead(new Error('Slow service failure'));
    await flushPromises();

    expect(wrapper.text()).toContain('Slow service failure');
    expect(wrapper.text()).toContain('current lifecycle status is unknown');
    expect(wrapper.text()).not.toContain('Loading saved runs');
    wrapper.unmount();
  });

  it('coalesces a retry requested during an active recovery poll', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let resolveRead!: (runs: BacktestRun[]) => void;
    vi.mocked(listBacktestRuns)
      .mockRejectedValueOnce(new Error('Service unavailable'))
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRead = resolve;
          }),
      )
      .mockResolvedValueOnce([run('active', { status: 'succeeded' })]);
    const wrapper = mountWorkspace();
    await flushPromises();

    expect(wrapper.get('[data-testid="workspace-refresh"]').text()).toBe(
      'Retry now',
    );
    vi.advanceTimersByTime(5000);
    await flushPromises();
    await wrapper.find('[data-testid="workspace-refresh"]').trigger('click');
    expect(listBacktestRuns).toHaveBeenCalledTimes(2);
    resolveRead([run('active', { status: 'running', metrics: null })]);
    await flushPromises();

    expect(listBacktestRuns).toHaveBeenCalledTimes(3);
    expect(
      wrapper.find('[data-testid="workspace-run-active"]').text(),
    ).toContain('succeeded');
    wrapper.unmount();
  });
});
