import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getBacktestBatch, listBacktestBatchEvents, listBacktestBatchMembers,
} from '@/api/backtesterClient';
import type { BacktestBatch, BacktestRun } from '@/types/backtesterContracts';
import BacktestBatches from '@/components/Backtest/BacktestBatches.vue';

vi.mock('@/api/backtesterClient', () => ({
  getBacktestBatch: vi.fn(), listBacktestBatchEvents: vi.fn(),
  listBacktestBatchMembers: vi.fn(),
}));

const batch: BacktestBatch = {
  batch_id: 'batch-1', submission_id: 'submit-1', status: 'queued',
  accepted_at_ms: 1_780_000_000_000, lifecycle_revision: 0,
  definition_schema_version: 1,
  accepted_definition: { schema_version: 1, shared_request: { start_ms: 1_714_521_600_000 },
    normalized_selections: { markets: [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
      timeframes: ['M1'], parameters: { fast_window: { mode: 'range', values: [5, 6],
        range: { start: 5, stop: 6, step: 1 } } }, allowed_directions: ['long_and_short'] } },
  strategy_metadata: { strategy_id: 'sma_crossover', strategy_version: 1,
    display_name: 'SMA crossover', parameters: [] },
  raw_count: 3, member_count: 2, excluded_count: 1,
  total_count: 2, settled_count: 0, executed_count: 0,
  outcome_counts: { queued: 2, running: 0, cancelling: 0, succeeded: 0,
    failed: 0, cancelled: 0 },
};

function member(ordinal: number): BacktestRun {
  return {
    run_id: `member-${ordinal}`, batch_id: 'batch-1', member_ordinal: ordinal,
    status: 'queued', submitted_at_ms: batch.accepted_at_ms, request_schema_version: 3,
    request: { symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M1',
      start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000, engine: 'vectorized',
      data_granularity: 'bar', initial_capital: 10_000,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1,
        parameters: { fast_window: 5 + ordinal } },
      execution: { signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
        allow_partial_fills: false, allowed_directions: 'long_and_short',
        trade_accounting_policy: 'average_cost', gap_policy: 'skip',
        intrabar_exit_policy: 'conservative', commission_bps: 0, slippage_bps: 0 },
      persist_result: false },
  };
}

describe('accepted batch inspection', () => {
  beforeEach(() => {
    vi.mocked(getBacktestBatch).mockReset().mockResolvedValue(batch);
    vi.mocked(listBacktestBatchMembers).mockReset().mockResolvedValue([member(0), member(1)]);
    vi.mocked(listBacktestBatchEvents).mockReset().mockResolvedValue([{ batch_id: 'batch-1',
      revision: 0, event_type: 'accepted', status: 'queued',
      occurred_at: '2026-09-26T00:00:00Z', reason: null }]);
  });

  it('shows one batch summary, saved definition, and actual ordered Ready members after reload', async () => {
    const reloaded = mount(BacktestBatches, { props: { batchId: 'batch-1' } });
    await flushPromises();
    expect(reloaded.text()).toContain('2 fixed members');
    expect(reloaded.text()).toContain('0 / 2 settled');
    expect(reloaded.text()).toContain('0 executed');
    expect(reloaded.find('[data-testid="workspace-batch-members"]').text()).toContain('member-1');
    expect(reloaded.findAll('[data-testid^="workspace-member-"]')).toHaveLength(2);
    expect(reloaded.text()).toContain('Accepted sweep settings and Strategy Metadata Snapshot');
    expect(reloaded.text()).not.toContain('0%');
    reloaded.unmount();
  });
});
