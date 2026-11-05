import {
  setupWorkspaceTests,
  seedBacktest,
  run,
  trade,
  fill,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchBacktestClosedTrades,
  fetchBacktestFills,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { BacktestClosedTrade } from '@/types/backtesterContracts';

function pendingTrades() {
  let resolve!: (trades: BacktestClosedTrade[]) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<BacktestClosedTrade[]>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return {
    promise,
    resolve,
    settle(outcome: 'success' | 'failure') {
      if (outcome === 'success') resolve([trade(0, 'long', 'signal')]);
      else reject(new Error('Old log unavailable'));
    },
  };
}

async function openFirstLog() {
  seedBacktest([run('first'), run('second')]);
  vi.mocked(fetchBacktestFills).mockResolvedValue([fill(0, 'sell')]);
  const wrapper = mountWorkspace(true);
  await flushPromises();
  await wrapper
    .get('[data-testid="workspace-backtest-first"]')
    .trigger('click');
  await flushPromises();
  await wrapper.get('[data-testid="workspace-member-first"]').trigger('click');
  await flushPromises();
  const action = wrapper.get('[data-testid="workspace-log-first"]');
  expect(action.attributes('aria-label')).toBe('View execution log for Run #1');
  await action.trigger('click');
  await flushPromises();
  expect(document.body.textContent).toContain('Loading execution log');
  expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
  return wrapper;
}

function logContent() {
  return document.body.querySelector('[data-testid="execution-log-drawer"]');
}

function expectSecondLog() {
  expect(document.body.textContent).toContain('Execution log · Run #2');
  expect(logContent()?.querySelector('.run-identity code')?.textContent).toBe(
    'second',
  );
  expect(logContent()?.textContent).toContain('short');
  expect(logContent()?.textContent).not.toContain('long');
  expect(logContent()?.textContent).not.toContain('Old log unavailable');
  expect(fetchBacktestClosedTrades).toHaveBeenLastCalledWith('second');
  expect(fetchBacktestFills).toHaveBeenLastCalledWith('second');
}

describe('Backtest Workspace execution-log races', () => {
  setupWorkspaceTests();

  it.each(['success', 'failure'] as const)(
    'ignores a late %s after closing a log and preserves later selection',
    async (outcome) => {
      const first = pendingTrades();
      vi.mocked(fetchBacktestClosedTrades).mockImplementation((id) =>
        id === 'first'
          ? first.promise
          : Promise.resolve([trade(1, 'short', 'stop_loss')]),
      );
      const wrapper = await openFirstLog();
      document.body
        .querySelector<HTMLButtonElement>('.n-drawer-header__close')!
        .click();
      await flushPromises();
      expect(logContent()).toBeNull();
      first.settle(outcome);
      await flushPromises();
      expect(logContent()).toBeNull();
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');

      await wrapper
        .get('[data-testid="workspace-member-second"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-log-second"]')
        .trigger('click');
      await flushPromises();
      expectSecondLog();
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('second');
    },
  );

  it.each(['success', 'failure'] as const)(
    'ignores a previous Run’s %s while the next log is still loading',
    async (outcome) => {
      const first = pendingTrades();
      const second = pendingTrades();
      vi.mocked(fetchBacktestClosedTrades).mockImplementation((id) =>
        id === 'first' ? first.promise : second.promise,
      );
      const wrapper = await openFirstLog();
      await wrapper
        .get('[data-testid="workspace-log-second"]')
        .trigger('click');
      await flushPromises();
      first.settle(outcome);
      await flushPromises();
      expect(
        logContent()?.querySelector('.run-identity code')?.textContent,
      ).toBe('second');
      expect(logContent()?.textContent).toContain('Loading execution log');
      expect(logContent()?.textContent).not.toContain('Old log unavailable');
      expect(logContent()?.querySelector('table')).toBeNull();
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');

      second.resolve([trade(1, 'short', 'stop_loss')]);
      await flushPromises();
      expectSecondLog();
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
    },
  );
});
