import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { flushPromises } from '@vue/test-utils';
import { useExecutionLogStore } from '@/stores/executionLogStore';
import { fetchExecutionLog } from '@/api/executionLogClient';
import type { ExecutionLogPage } from '@/types/backtest/executionLog';
import { backtestRun } from '../api/backtesterClient.fixtures';
import { deferred, logPage } from '../executionLogFixtures';
vi.mock('@/api/executionLogClient', () => ({ fetchExecutionLog: vi.fn() }));
beforeEach(() => {
  setActivePinia(createPinia());
  vi.mocked(fetchExecutionLog).mockReset();
});

describe('execution log selection and paging', () => {
  it(
    'starts hidden, strips diagnostics, preloads one page, ' +
      'and reads each requested page',
    async () => {
      const store = useExecutionLogStore();
      expect(store.selectedRun).toBeNull();
      expect(store.consumesSpace).toBe(false);
      vi.mocked(fetchExecutionLog).mockImplementation(async (id, page) =>
        logPage(id, page),
      );
      store.selectRun(
        backtestRun({ diagnostics: { order_events: [{ huge: true }] } }),
        false,
      );
      await flushPromises();
      expect(store.isOpen).toBe(false);
      expect(store.selectedRun).not.toHaveProperty('diagnostics');
      expect(store.items).toHaveLength(10);
      store.setPage(3);
      await flushPromises();
      expect(fetchExecutionLog).toHaveBeenLastCalledWith(
        'run-123',
        3,
        false,
        expect.any(AbortSignal),
      );
      expect(store.items).toHaveLength(3);
      store.setPage(4);
      expect(fetchExecutionLog).toHaveBeenCalledTimes(2);
      store.setIncludeUnexecuted(true);
      await flushPromises();
      expect(store.page).toBe(1);
      expect(fetchExecutionLog).toHaveBeenLastCalledWith(
        'run-123',
        1,
        true,
        expect.any(AbortSignal),
      );
      store.selectRun(backtestRun());
      expect(store.isOpen).toBe(true);
      expect(fetchExecutionLog).toHaveBeenCalledTimes(3);
    },
  );
  it.each(['resolve', 'reject'] as const)(
    'ignores an old run request that later %ss',
    async (outcome) => {
      const old = deferred<ExecutionLogPage>();
      vi.mocked(fetchExecutionLog)
        .mockReturnValueOnce(old.promise)
        .mockResolvedValueOnce(logPage('new'));
      const store = useExecutionLogStore();
      store.selectRun(backtestRun());
      const oldSignal = vi.mocked(fetchExecutionLog).mock.calls[0][3]!;
      store.selectRun(backtestRun({ run_id: 'new' }));
      await flushPromises();
      expect(oldSignal.aborted).toBe(true);
      if (outcome === 'resolve') old.resolve(logPage());
      else old.reject(new Error('old failure'));
      await flushPromises();
      expect(store.selectedRun?.run_id).toBe('new');
      expect(store.error).toBeNull();
      expect(store.items).toEqual(logPage('new').items);
    },
  );
  it('keeps query identity on retry and clears pending results on removal', async () => {
    vi.mocked(fetchExecutionLog)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(logPage());
    const store = useExecutionLogStore();
    store.selectRun(backtestRun());
    await flushPromises();
    expect(store.error).toBe('offline');
    await store.retry();
    expect(store.error).toBeNull();
    const pending = deferred<ExecutionLogPage>();
    vi.mocked(fetchExecutionLog).mockReturnValueOnce(pending.promise);
    store.setPage(2);
    store.clear();
    pending.resolve(logPage('run-123', 2));
    await flushPromises();
    expect(store.selectedRun).toBeNull();
    expect(store.items).toEqual([]);
    expect(store.consumesSpace).toBe(false);
  });
});
