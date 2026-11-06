import {
  setupRoutingTests,
  openWorkspace,
  backtest,
} from './backtestWorkspaceRoutingFixtures';
import router from '@/router';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  getBacktest,
  getBacktestRun,
  listBacktests,
} from '@/api/backtesterClient';
import { HttpResponseError } from '@/api/http';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { emitBacktestChange } from '../backtestEventSocket';

describe('Backtest workspace routes', () => {
  setupRoutingTests();

  it('loads a linked Backtest without selecting a Run', async () => {
    const wrapper = await openWorkspace();
    expect(getBacktest).toHaveBeenCalledWith('backtest-1');
    expect(wrapper.get('h3').text()).toBe('Unnamed backtest');
    expect(wrapper.get('[aria-label="Current Backtest"]').isVisible()).toBe(
      true,
    );
    expect(useBacktestWorkspaceStore().selectedRunId).toBeNull();
    expect(getBacktestRun).not.toHaveBeenCalled();
  });

  it('opens history rows in the address bar and returns through browser history', async () => {
    const wrapper = await openWorkspace('/backtests');
    await wrapper
      .get('[data-testid="workspace-backtest-backtest-1"]')
      .trigger('click');
    await flushPromises();
    expect(window.location.pathname).toBe('/backtests/backtest-1');
    window.history.back();
    await vi.waitFor(() => {
      expect(router.currentRoute.value.path).toBe('/backtests');
    });
    await flushPromises();
    expect(wrapper.get('[aria-label="Current Backtest"]').isVisible()).toBe(
      false,
    );
    window.history.forward();
    await vi.waitFor(() => {
      expect(router.currentRoute.value.params.id).toBe('backtest-1');
    });
    await flushPromises();
    expect(wrapper.get('[aria-label="Current Backtest"]').isVisible()).toBe(
      true,
    );
  });

  it('keeps Run selection in memory and the Backtesting button opens the overview', async () => {
    const wrapper = await openWorkspace();
    await wrapper
      .get('[data-testid="workspace-member-member-0"]')
      .trigger('click');
    await flushPromises();
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('member-0');
    expect(window.location.pathname).toBe('/backtests/backtest-1');

    await wrapper.get('[aria-label="Return to Chart"]').trigger('click');
    await flushPromises();
    expect(window.location.pathname).toBe('/');
    window.history.back();
    await vi.waitFor(() => {
      expect(router.currentRoute.value.params.id).toBe('backtest-1');
    });
    await flushPromises();
    expect(useBacktestWorkspaceStore().selectedRunId).toBe('member-0');

    await wrapper.get('[aria-label="Return to Chart"]').trigger('click');
    await flushPromises();
    await wrapper.get('[aria-label="Open Backtests"]').trigger('click');
    await flushPromises();
    expect(window.location.pathname).toBe('/backtests');
    await wrapper
      .get('[data-testid="workspace-backtest-backtest-1"]')
      .trigger('click');
    await flushPromises();
    expect(useBacktestWorkspaceStore().selectedRunId).toBeNull();
  });

  it('replaces a missing Backtest link with charts even if history cannot load', async () => {
    vi.mocked(listBacktests).mockRejectedValue(new Error('Offline'));
    vi.mocked(getBacktest).mockRejectedValue(
      new HttpResponseError('Backtest not found', 404),
    );
    const wrapper = await openWorkspace('/backtests');
    await router.push('/backtests/missing');
    await flushPromises();
    expect(window.location.pathname).toBe('/');
    expect(wrapper.text()).toContain('Chart page');
    window.history.back();
    await vi.waitFor(() => {
      expect(router.currentRoute.value.path).toBe('/backtests');
    });
  });

  it.each([
    new Error('Network unavailable'),
    new HttpResponseError('Service unavailable', 503),
  ])('retains the Backtest URL for %s', async (error) => {
    vi.mocked(getBacktest).mockRejectedValue(error);
    const wrapper = await openWorkspace();
    expect(window.location.pathname).toBe('/backtests/backtest-1');
    expect(wrapper.text()).toContain(error.message);
  });

  it('keeps a valid detail page when an older history response omits it', async () => {
    vi.mocked(listBacktests).mockResolvedValue([]);
    const wrapper = await openWorkspace();
    expect(window.location.pathname).toBe('/backtests/backtest-1');
    expect(wrapper.get('h3').text()).toBe('Unnamed backtest');
  });

  it('redirects when the inspected Backtest disappears during live updates', async () => {
    await openWorkspace();
    vi.mocked(listBacktests).mockResolvedValue([]);
    vi.mocked(getBacktest).mockRejectedValue(
      new HttpResponseError('Backtest not found', 404),
    );
    emitBacktestChange();
    await flushPromises();
    expect(window.location.pathname).toBe('/');
  });

  it('ignores a missing response from the previous Backtest', async () => {
    let rejectMissing!: (error: Error) => void;
    vi.mocked(getBacktest).mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          rejectMissing = reject;
        }),
    );
    const wrapper = await openWorkspace('/backtests/missing');
    await router.push(`/backtests/${backtest.backtest_id}`);
    await flushPromises();
    rejectMissing(new HttpResponseError('Backtest not found', 404));
    await flushPromises();
    expect(window.location.pathname).toBe('/backtests/backtest-1');
    expect(wrapper.get('h3').text()).toBe('Unnamed backtest');
  });

  it('invalidates a missing cached Backtest without leaving the overview', async () => {
    let rejectMissing!: (error: Error) => void;
    const missing = new HttpResponseError('Backtest not found', 404);
    vi.mocked(getBacktest)
      .mockRejectedValue(missing)
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectMissing = reject;
          }),
      );
    const wrapper = await openWorkspace();
    await wrapper
      .get('[data-testid="workspace-history-return"]')
      .trigger('click');
    await flushPromises();
    rejectMissing(missing);
    await flushPromises();
    expect(window.location.pathname).toBe('/backtests');
    window.history.back();
    await vi.waitFor(() => {
      expect(router.currentRoute.value.path).toBe('/');
    });
    expect(getBacktest).toHaveBeenCalledTimes(2);
  });
});
