import {
  setupWorkspaceTests,
  run,
  mountWorkspace,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';

import { NSelect } from 'naive-ui';

import { describe, expect, it, vi } from 'vitest';

import {
  getBacktestBatch,
  listBacktestBatchEvents,
  listBacktestBatchMembers,
  listBacktestBatches,
  listBacktestRuns,
} from '@/api/backtesterClient';

import type { BacktestBatch } from '@/types/backtesterContracts';

describe('production Backtest Workspace: history-batches', () => {
  setupWorkspaceTests();
  it('filters batches and standalone runs in one history without member rows', async () => {
    const standalone = run('standalone');
    const memberRun = run('member-0', {
      batch_id: 'batch-1',
      member_ordinal: 0,
      status: 'failed',
      metrics: null,
    });
    const batch = {
      batch_id: 'batch-1',
      submission_id: 'submit-1',
      status: 'completed',
      accepted_at_ms: 1_780_000_000_000,
      lifecycle_revision: 1,
      started_at_ms: 1_780_000_001_000,
      completed_at_ms: 1_780_000_002_000,
      active_member_ordinal: null,
      next_member_ordinal: null,
      definition_schema_version: 1,
      accepted_definition: {
        schema_version: 1,
        shared_request: {
          start_ms: 1_714_521_600_000,
          end_ms: 1_714_608_000_000,
        },
        normalized_selections: {
          markets: [
            { symbol_id: 2, symbol: 'GBPUSD', exchange: 'FX' },
            { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' },
          ],
          timeframes: ['H1', 'M15'],
          parameters: {},
          allowed_directions: ['long_and_short'],
        },
      },
      strategy_metadata: {
        strategy_id: 'breakout',
        strategy_version: 1,
        display_name: 'Breakout',
        parameters: [],
      },
      raw_count: 2,
      member_count: 1,
      excluded_count: 1,
      total_count: 1,
      settled_count: 1,
      executed_count: 1,
      outcome_counts: {
        queued: 0,
        running: 0,
        cancelling: 0,
        succeeded: 0,
        failed: 1,
        cancelled: 0,
      },
      has_failed_members: true,
      markets: ['GBPUSD'],
      exchanges: ['FX'],
      market_contexts: [{ symbol: 'GBPUSD', exchange: 'FX' }],
      timeframes: ['H1'],
      strategy_id: 'breakout',
      strategy_version: 1,
    } as BacktestBatch;
    vi.mocked(listBacktestRuns).mockResolvedValue([standalone, memberRun]);
    vi.mocked(listBacktestBatches).mockResolvedValue([batch]);
    vi.mocked(getBacktestBatch).mockResolvedValue(batch);
    vi.mocked(listBacktestBatchMembers).mockResolvedValue([memberRun]);
    vi.mocked(listBacktestBatchEvents).mockResolvedValue([
      {
        batch_id: 'batch-1',
        revision: 0,
        event_type: 'accepted',
        prior_status: null,
        status: 'queued',
        occurred_at_ms: batch.accepted_at_ms,
        trigger_run_id: null,
        reason: null,
      },
    ]);
    const wrapper = mountWorkspace(true);
    await flushPromises();
    const history = () => wrapper.find('[data-testid="workspace-history"]');
    expect(history().findAll('tbody tr')).toHaveLength(2);
    expect(
      history().find('[data-testid="workspace-run-member-0"]').exists(),
    ).toBe(false);
    expect(
      history().find('[data-testid="workspace-batch-batch-1"]').text(),
    ).toContain('1 / 1');
    expect(
      history().find('[data-testid="workspace-batch-batch-1"]').text(),
    ).toContain('1 failed');
    await history()
      .find('[data-testid="workspace-batch-batch-1"]')
      .trigger('click');
    await flushPromises();
    expect(
      wrapper
        .find('[data-testid="workspace-member-member-0"] .run-identity span')
        .text(),
    ).toBe('Run #1');
    expect(listBacktestBatchMembers).toHaveBeenCalledWith('batch-1');

    await wrapper
      .find('[data-testid="workspace-search"] input')
      .setValue('submit-1');
    expect(
      history().find('[data-testid="workspace-batch-batch-1"]').exists(),
    ).toBe(true);
    expect(
      history().find('[data-testid="workspace-run-standalone"]').exists(),
    ).toBe(false);
    await wrapper.find('[data-testid="workspace-search"] input').setValue('');

    for (const [index, value] of [
      [0, 'completed'],
      [1, 'batch'],
      [2, 'FX:GBPUSD'],
      [3, 'breakout'],
      [4, 'H1'],
      [5, 'with_failed'],
    ] as const) {
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', value);
      await wrapper.vm.$nextTick();
      expect(
        history().find('[data-testid="workspace-batch-batch-1"]').exists(),
      ).toBe(true);
      expect(
        history().find('[data-testid="workspace-run-standalone"]').exists(),
      ).toBe(false);
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', 'all');
      await wrapper.vm.$nextTick();
    }
    for (const [index, excluded] of [
      [2, 'FX:EURUSD'],
      [4, 'M15'],
    ] as const) {
      wrapper
        .findAllComponents(NSelect)
        [index].vm.$emit('update:value', excluded);
      await wrapper.vm.$nextTick();
      expect(
        history().find('[data-testid="workspace-batch-batch-1"]').exists(),
      ).toBe(false);
      wrapper.findAllComponents(NSelect)[index].vm.$emit('update:value', 'all');
      await wrapper.vm.$nextTick();
    }
    const timeframeHeader = wrapper
      .findAll('th')
      .find((header) => header.text().includes('Timeframe'));
    const orderedRows = () =>
      history()
        .findAll('tbody tr')
        .map((row) => row.attributes('data-testid'));
    await timeframeHeader?.trigger('click');
    expect(orderedRows()).toEqual([
      'workspace-batch-batch-1',
      'workspace-run-standalone',
    ]);
    await timeframeHeader?.trigger('click');
    expect(orderedRows()).toEqual([
      'workspace-run-standalone',
      'workspace-batch-batch-1',
    ]);
    wrapper.unmount();
  });
});
