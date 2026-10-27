import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktestBatch,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  controlBacktestBatch,
} from '@/api/backtesterClient';
import {
  isBacktestBatch,
  type BacktestBatch,
} from '@/types/backtesterContracts';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';

vi.mock('@/api/backtesterClient', () => ({
  controlBacktestBatch: vi.fn(),
  renameExperiment: vi.fn(),
  getBacktestBatch: vi.fn(),
  listBacktestBatchEvents: vi.fn(),
  listBacktestBatchMembers: vi.fn(),
}));

import { batch, member } from './backtestBatchFixtures';

describe('accepted batch inspection: inspection', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(controlBacktestBatch).mockReset();
    vi.mocked(getBacktestBatch).mockReset().mockResolvedValue(batch);
    vi.mocked(listBacktestBatchMembers)
      .mockReset()
      .mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestBatchEvents)
      .mockReset()
      .mockResolvedValue([
        {
          batch_id: 'batch-1',
          revision: 0,
          event_type: 'accepted',
          status: 'queued',
          prior_status: null,
          occurred_at_ms: batch.accepted_at_ms,
          trigger_run_id: null,
          reason: null,
        },
      ]);
  });

  it('validates actual-member context and aggregate failure projection', () => {
    expect(isBacktestBatch(batch)).toBe(true);
    expect(isBacktestBatch({ ...batch, has_failed_members: true })).toBe(false);
    expect(isBacktestBatch({ ...batch, market_contexts: [] })).toBe(false);
  });

  it('emits actual members to the workspace comparison table', async () => {
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(wrapper.get('h3').text()).toBe('Unnamed parameter sweep');
    expect(wrapper.emitted('members')?.[0]).toEqual([
      'batch-1',
      [member(0), member(1)],
    ]);
    expect(
      wrapper.find('[data-testid="workspace-batch-members"]').exists(),
    ).toBe(false);
    wrapper.unmount();
  });

  it('shows the saved experiment name again after reloading detail', async () => {
    vi.mocked(getBacktestBatch).mockResolvedValue({
      ...batch,
      name: 'Sweep research',
    });
    for (let reload = 0; reload < 2; reload += 1) {
      const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
      await flushPromises();
      expect(wrapper.get('h3').text()).toBe('Sweep research');
      wrapper.unmount();
    }
  });

  it('does not discard a batch read that takes longer than a poll interval', async () => {
    vi.useFakeTimers();
    let resolve!: (batch: BacktestBatch) => void;
    vi.mocked(getBacktestBatch).mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const wrapper = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    vi.advanceTimersByTime(10_000);
    await flushPromises();
    expect(getBacktestBatch).toHaveBeenCalledTimes(1);
    resolve(batch);
    await flushPromises();
    expect(wrapper.emitted('members')).toHaveLength(1);
    wrapper.unmount();
    vi.useRealTimers();
  });

  it(
    'shows one batch summary, saved definition, and actual ordered ' +
      'Ready members after reload',
    async () => {
      const reloaded = mount(BacktestBatches, {
        props: { batchId: 'batch-1' },
      });
      await flushPromises();
      expect(reloaded.text()).toContain('2 of 3 combinations');
      expect(
        reloaded.get('[role="progressbar"]').attributes('aria-valuetext'),
      ).toContain('0 / 2 settled');
      expect(reloaded.text()).toContain('0 executed');
      expect(reloaded.emitted('members')?.[0]).toEqual([
        'batch-1',
        [member(0), member(1)],
      ]);
      expect(
        reloaded.find('[data-testid="workspace-batch-members"]').exists(),
      ).toBe(false);
      expect(reloaded.text()).toContain(
        'Full saved definition and strategy metadata',
      );
      expect(
        reloaded.get('[role="progressbar"]').attributes('aria-valuenow'),
      ).toBe('0');
      reloaded.unmount();
    },
  );
});
