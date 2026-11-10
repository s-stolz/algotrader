import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchExecutionLog } from '@/api/executionLogClient';
import { jsonResponse } from './backtesterClient.fixtures';
import { logPage, orderItem } from '../executionLogFixtures';
afterEach(() => vi.unstubAllGlobals());
describe('execution log transport', () => {
  it('requests only the requested mixed page with cancellation support', async () => {
    const page = logPage('run/id', 2);
    page.items[0] = orderItem();
    const fetch = vi.fn().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal('fetch', fetch);
    const abort = new AbortController();
    expect(await fetchExecutionLog('run/id', 2, true, abort.signal)).toEqual(
      page,
    );
    expect(fetch).toHaveBeenCalledWith(
      '/api/backtester/backtests/runs/run%2Fid/execution-log' +
        '?page=2&page_size=10&include_unexecuted=true',
      { signal: abort.signal },
    );
  });
  it.each(['run', 'page', 'size', 'count', 'order', 'unrequested-order'])(
    'rejects an invalid %s response',
    async (failure) => {
      const page = logPage();
      if (failure === 'run') page.run_id = 'other';
      if (failure === 'page') page.page = 2;
      if (failure === 'size') page.page_size = 20;
      if (failure === 'count') page.items.pop();
      if (failure === 'order') page.items.reverse();
      if (failure === 'unrequested-order') page.items[0] = orderItem();
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(page)));
      await expect(fetchExecutionLog('run-123', 1, false)).rejects.toThrow(
        'Invalid execution log response',
      );
    },
  );
});
