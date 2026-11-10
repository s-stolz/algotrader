import {
  setupWorkspaceTests,
  seedBacktest,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { fetchExecutionLog } from '@/api/executionLogClient';
import { useExecutionLogStore } from '@/stores/executionLogStore';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { deferred, logPage } from '../executionLogFixtures';
import type { ExecutionLogPage } from '@/types/backtest/executionLog';

describe('Backtest Workspace paginated execution logs', () => {
  setupWorkspaceTests();
  it.each(['resolve', 'reject'] as const)(
    'selects the action run without changing inspected run and ignores stale %s',
    async (outcome) => {
      const first = deferred<ExecutionLogPage>();
      vi.mocked(fetchExecutionLog).mockImplementation((id) =>
        id === 'first' ? first.promise : Promise.resolve(logPage('second')),
      );
      seedBacktest([run('first'), run('second')]);
      const wrapper = mountWorkspace(true);
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-backtest-first"]')
        .trigger('click');
      await flushPromises();
      await wrapper
        .get('[data-testid="workspace-member-first"]')
        .trigger('click');
      await flushPromises();
      await wrapper.get('[data-testid="workspace-log-first"]').trigger('click');
      const store = useExecutionLogStore();
      expect(store.selectedRun?.run_id).toBe('first');
      expect(store.isOpen).toBe(true);
      expect(store.loading).toBe(true);
      await wrapper
        .get('[data-testid="workspace-log-second"]')
        .trigger('click');
      await flushPromises();
      if (outcome === 'resolve') first.resolve(logPage('first'));
      else first.reject(new Error('old error'));
      await flushPromises();
      expect(store.selectedRun?.run_id).toBe('second');
      expect(store.items).toEqual(logPage('second').items);
      expect(store.error).toBeNull();
      expect(useBacktestWorkspaceStore().selectedRunId).toBe('first');
      expect(fetchExecutionLog).toHaveBeenLastCalledWith(
        'second',
        1,
        false,
        expect.any(AbortSignal),
      );
      wrapper.unmount();
    },
  );
});
