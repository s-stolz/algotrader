import { onTestFinished } from 'vitest';
import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import BacktestQueueHealth from '@/components/Backtest/BacktestQueueHealth.vue';
import type {
  Backtest,
  BacktestQueueSnapshot,
} from '@/types/backtesterContracts';
export const PopoverStub = defineComponent({
  props: ['show'],
  emits: ['update:show'],
  template:
    '<div><div @click="$emit(\'update:show\', !show)"><slot ' +
    'name="trigger" /></div><div v-if="show"><slot /></div></div>',
});
export async function openQueue(props: { backtests?: Backtest[] } = {}) {
  const wrapper = mount(BacktestQueueHealth, {
    props,
    global: { stubs: { BasePopover: PopoverStub } },
  });
  onTestFinished(() => wrapper.unmount());
  await flushPromises();
  await wrapper.get('[data-testid="queue-toggle"]').trigger('click');
  return wrapper;
}

export const backtest: Backtest = {
  backtest_id: 'backtest-1',
  submission_id: 'submit-1',
  status: 'queued',
  accepted_at_ms: 1_780_000_000_000,
  lifecycle_revision: 0,
  started_at_ms: null,
  completed_at_ms: null,
  active_run_ordinal: 0,
  next_run_ordinal: 0,
  definition_schema_version: 1,
  accepted_definition: {
    schema_version: 1,
    shared_request: { start_ms: 1_714_521_600_000 },
    normalized_selections: {
      markets: [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
      timeframes: ['M1'],
      parameters: {
        fast_window: {
          mode: 'range',
          values: [5, 6],
          range: { start: 5, stop: 6, step: 1 },
        },
      },
      allowed_directions: ['long_and_short'],
    },
  },
  strategy_metadata: {
    strategy_id: 'sma_crossover',
    strategy_version: 1,
    display_name: 'SMA crossover',
    parameters: [],
  },
  raw_count: 3,
  member_count: 2,
  excluded_count: 1,
  total_count: 2,
  settled_count: 0,
  executed_count: 0,
  outcome_counts: {
    queued: 2,
    running: 0,
    cancelling: 0,
    succeeded: 0,
    failed: 0,
    cancelled: 0,
  },
  has_failed_members: false,
  markets: ['EURUSD'],
  exchanges: ['FX'],
  market_contexts: [{ symbol: 'EURUSD', exchange: 'FX' }],
  timeframes: ['M1'],
  strategy_id: 'sma_crossover',
  strategy_version: 1,
};

export const NOW = 1_780_922_100_000;
export const healthySnapshot: BacktestQueueSnapshot = {
  snapshot_at_ms: NOW,
  active_run: {
    run_id: 'long-run',
    started_at_ms: NOW - 120_000,
    backtest_id: 'backtest-1',
    run_ordinal: 0,
  },
  last_heartbeat_ms: NOW - 1000,
  availability: 'healthy',
  stale_after_ms: 30_000,
  operational_faults: [],
  queued: [
    {
      backtest_id: 'waiting',
      submitted_at_ms: NOW - 60_000,
      estimated_position: 1,
      next_run_ordinal: 0,
      outcome_counts: {
        queued: 1,
        running: 0,
        cancelling: 0,
        succeeded: 0,
        failed: 0,
        cancelled: 0,
      },
    },
  ],
};
