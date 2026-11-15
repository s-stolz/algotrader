import {
  setupWorkspaceTests,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import { listBacktests } from '@/api/backtesterClient';

describe('production Backtest Workspace: refresh-recovery', () => {
  setupWorkspaceTests();
  it('shows a retryable error for an unavailable history read', async () => {
    vi.mocked(listBacktests).mockRejectedValue(
      new Error('Service unavailable'),
    );
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Couldn’t load backtests.',
    );
    wrapper.unmount();
  });

  it('shows a slow read error after several seconds instead of loading forever', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    let rejectRead!: (error: Error) => void;
    vi.mocked(listBacktests).mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          rejectRead = reject;
        }),
    );
    const wrapper = mountWorkspace();
    await flushPromises();

    vi.advanceTimersByTime(6000);
    expect(listBacktests).toHaveBeenCalledOnce();
    rejectRead(new Error('Slow service failure'));
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Couldn’t load backtests.',
    );
    wrapper.unmount();
  });
});
