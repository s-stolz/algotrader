import { installBacktestSocket } from '../../backtestEventSocket';
import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktest,
  listBacktestEvents,
  listBacktestMembers,
  controlBacktest,
} from '@/api/backtesterClient';
import BacktestOverview from '@/components/Backtest/BacktestOverview.vue';

vi.mock('@/api/backtesterClient', () => ({
  controlBacktest: vi.fn(),
  renameExperiment: vi.fn(),
  getBacktest: vi.fn(),
  listBacktestEvents: vi.fn(),
  listBacktestMembers: vi.fn(),
}));

import { backtest, member } from './backtestOverviewFixtures';

describe('accepted backtest inspection: commands', () => {
  beforeEach(() => {
    installBacktestSocket();
    setActivePinia(createPinia());
    vi.mocked(controlBacktest).mockReset();
    vi.mocked(getBacktest).mockReset().mockResolvedValue(backtest);
    vi.mocked(listBacktestMembers)
      .mockReset()
      .mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestEvents)
      .mockReset()
      .mockResolvedValue([
        {
          backtest_id: 'backtest-1',
          revision: 0,
          event_type: 'accepted',
          status: 'queued',
          prior_status: null,
          occurred_at_ms: backtest.accepted_at_ms,
          trigger_run_id: null,
          reason: null,
        },
      ]);
  });

  it('offers legal pause and resume controls and refreshes after command acceptance', async () => {
    vi.mocked(controlBacktest).mockResolvedValueOnce({
      backtest_id: 'backtest-1',
      status: 'paused',
      lifecycle_revision: 1,
    });
    vi.mocked(getBacktest)
      .mockResolvedValueOnce(backtest)
      .mockResolvedValue({
        ...backtest,
        status: 'paused',
        lifecycle_revision: 1,
      });
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(controlBacktest).toHaveBeenCalledWith(
      'backtest-1',
      'pause',
      expect.any(String),
    );
    expect(wrapper.text()).toContain('Backtest paused.');
    expect(wrapper.get('.header-actions button').text()).toBe(
      'Resume Backtest',
    );
    expect(wrapper.get('p[role="status"]').text()).not.toContain('%');
    wrapper.unmount();
  });

  it('cancels an executing backtest and keeps its active member visibly unsettled', async () => {
    const running = {
      ...backtest,
      status: 'running' as const,
      active_run_ordinal: 0,
      outcome_counts: { ...backtest.outcome_counts, queued: 1, running: 1 },
    };
    const cancelling = {
      ...running,
      status: 'cancelling' as const,
      cancel_requested_at_ms: backtest.accepted_at_ms + 1,
      cancellation_source: 'user',
      cancellation_reason: 'user_requested',
      lifecycle_revision: 2,
      next_run_ordinal: null,
      outcome_counts: {
        ...backtest.outcome_counts,
        queued: 0,
        running: 0,
        cancelling: 1,
        cancelled: 1,
      },
      settled_count: 1,
    };
    vi.mocked(getBacktest)
      .mockResolvedValueOnce(running)
      .mockResolvedValue(cancelling);
    vi.mocked(listBacktestMembers)
      .mockResolvedValueOnce([{ ...member(0), status: 'running' }, member(1)])
      .mockResolvedValue([
        {
          ...member(0),
          status: 'cancelling',
          cancel_requested_at_ms: backtest.accepted_at_ms + 1,
          cancellation_source: 'backtest',
          cancellation_reason: 'backtest_cancel_requested',
        },
        {
          ...member(1),
          status: 'cancelled',
          cancel_requested_at_ms: backtest.accepted_at_ms + 1,
          completed_at_ms: backtest.accepted_at_ms + 1,
          cancellation_source: 'backtest',
          cancellation_reason: 'backtest_cancel_requested',
        },
      ]);
    vi.mocked(controlBacktest).mockImplementation(
      async (_id, _command, commandId) => ({
        backtest_id: 'backtest-1',
        command_id: commandId,
        status: 'cancelling',
        lifecycle_revision: 2,
      }),
    );
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    await wrapper
      .get('[data-testid="workspace-cancel-backtest"]')
      .trigger('click');
    await flushPromises();
    expect(controlBacktest).toHaveBeenCalledWith(
      'backtest-1',
      'cancel',
      expect.any(String),
    );
    expect(
      wrapper.get('[role="progressbar"]').attributes('aria-valuetext'),
    ).toContain('1 / 2 settled');
    expect(wrapper.text()).not.toContain('0 executed');
    expect(wrapper.text()).toContain('Cancellation will finish after cleanup');
    expect(wrapper.text()).toContain('Cancellation accepted:');
    expect(
      wrapper.find('[data-testid="workspace-cancel-backtest"]').exists(),
    ).toBe(false);
    expect(wrapper.emitted('cancelled')).toHaveLength(1);
    wrapper.unmount();
  });

  it('shows draining state and retries a failed command with the same identity', async () => {
    const draining = {
      ...backtest,
      status: 'pausing' as const,
      lifecycle_revision: 2,
      active_run_ordinal: 0,
    };
    vi.mocked(getBacktest).mockResolvedValue(draining);
    vi.mocked(controlBacktest)
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValueOnce({
        backtest_id: 'backtest-1',
        status: 'running',
        lifecycle_revision: 3,
      });
    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    expect(wrapper.text()).toContain('Pausing after the active run finishes.');
    expect(wrapper.get('.header-actions button').text()).toBe(
      'Resume Backtest',
    );
    expect(wrapper.get('p[role="status"]').text()).not.toContain('%');
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Connection lost');
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    const calls = vi.mocked(controlBacktest).mock.calls;
    expect(calls[0][2]).toBe(calls[1][2]);
    wrapper.unmount();
  });

  it(
    'retains a pending Pause identity when member cancellation ' +
      'advances the backtest revision',
    async () => {
      vi.mocked(getBacktest)
        .mockResolvedValueOnce(backtest)
        .mockResolvedValue({
          ...backtest,
          status: 'queued',
          lifecycle_revision: 1,
        });
      vi.mocked(listBacktestEvents)
        .mockResolvedValueOnce([
          {
            backtest_id: 'backtest-1',
            revision: 0,
            event_type: 'accepted',
            status: 'queued',
            prior_status: null,
            occurred_at_ms: backtest.accepted_at_ms,
            trigger_run_id: null,
            reason: null,
          },
        ])
        .mockResolvedValue([
          {
            backtest_id: 'backtest-1',
            revision: 1,
            event_type: 'member_cancelled',
            status: 'queued',
            prior_status: 'queued',
            occurred_at_ms: backtest.accepted_at_ms + 1,
            trigger_run_id: 'member-0',
            reason: 'user_requested',
            command_id: null,
          },
        ]);
      vi.mocked(controlBacktest).mockRejectedValue(
        new Error('Connection lost'),
      );
      const wrapper = mount(BacktestOverview, {
        props: { backtestId: 'backtest-1' },
      });
      await flushPromises();
      await wrapper.get('.header-actions button').trigger('click');
      await flushPromises();
      await wrapper.get('.header-actions button').trigger('click');
      await flushPromises();
      const calls = vi.mocked(controlBacktest).mock.calls;
      expect(calls).toHaveLength(2);
      expect(calls[0][2]).toBe(calls[1][2]);
      wrapper.unmount();
    },
  );

  it('uses a new Pause identity after a lost response, observed pause, and Resume', async () => {
    vi.mocked(getBacktest)
      .mockResolvedValueOnce(backtest)
      .mockResolvedValueOnce({
        ...backtest,
        status: 'paused',
        lifecycle_revision: 1,
      })
      .mockResolvedValueOnce({
        ...backtest,
        status: 'running',
        lifecycle_revision: 2,
      })
      .mockResolvedValue({
        ...backtest,
        status: 'paused',
        lifecycle_revision: 3,
      });
    vi.mocked(controlBacktest)
      .mockRejectedValueOnce(new Error('Pause response lost'))
      .mockResolvedValueOnce({
        backtest_id: 'backtest-1',
        status: 'running',
        lifecycle_revision: 2,
      })
      .mockResolvedValueOnce({
        backtest_id: 'backtest-1',
        status: 'paused',
        lifecycle_revision: 3,
      });

    const wrapper = mount(BacktestOverview, {
      props: { backtestId: 'backtest-1' },
    });
    await flushPromises();
    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(wrapper.get('.header-actions button').text()).toBe(
      'Resume Backtest',
    );
    expect(wrapper.text()).toContain('revision 1');

    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    expect(wrapper.get('.header-actions button').text()).toBe('Pause Backtest');
    expect(wrapper.text()).toContain('revision 2');

    await wrapper.get('.header-actions button').trigger('click');
    await flushPromises();
    const calls = vi.mocked(controlBacktest).mock.calls;
    expect(calls.map(([, , identity]) => identity)).toHaveLength(3);
    expect(calls.map(([, command]) => command)).toEqual([
      'pause',
      'resume',
      'pause',
    ]);
    expect(calls[2][2]).not.toBe(calls[0][2]);
    expect(wrapper.text()).toContain('revision 3');
    expect(wrapper.text()).toContain('Backtest paused.');
    wrapper.unmount();
  });
});
