import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  deleteBacktestRun,
  fetchBacktestClosedTrades,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { useBacktestOverlayStore } from '@/stores/backtestOverlayStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestRun } from '@/types/backtesterContracts';
import type { Market } from '@/types/contracts';
import { STORAGE_KEYS } from '@/utils/localStorage';

import BacktestRunHistoryModal from '@/components/TopBar/Modals/BacktestRunHistoryModal.vue';

vi.mock('@/api/backtesterClient', () => ({
  deleteBacktestRun: vi.fn(),
  fetchBacktestClosedTrades: vi.fn(),
  getBacktestRun: vi.fn(),
  listBacktestRuns: vi.fn(),
}));

const eurUsdMarket: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const BaseModalStub = defineComponent({
  name: 'BaseModal',
  setup(_, { expose, slots }) {
    expose({ close: () => undefined });

    return () => h('section', { class: 'base-modal' }, [
      slots.default?.(),
      slots.footer?.(),
    ]);
  },
});

const NButtonStub = defineComponent({
  name: 'NButton',
  props: {
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      disabled: props.disabled,
      onClick: (event: MouseEvent) => {
        if (!props.disabled) {
          emit('click', event);
        }
      },
    }, slots.default?.());
  },
});

const NInputStub = defineComponent({
  name: 'NInput',
  props: {
    value: {
      type: String,
      default: '',
    },
    placeholder: {
      type: String,
      default: '',
    },
    inputProps: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit, slots }) {
    return () => h('input', {
      ...attrs,
      ...props.inputProps,
      placeholder: props.placeholder,
      value: props.value,
      onInput: (event: Event) => {
        emit('update:value', (event.target as HTMLInputElement).value);
      },
    }, slots.default?.());
  },
});

describe('BacktestRunHistoryModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.mocked(deleteBacktestRun).mockReset();
    vi.mocked(fetchBacktestClosedTrades).mockReset();
    vi.mocked(getBacktestRun).mockReset();
    vi.mocked(listBacktestRuns).mockReset();
    vi.mocked(deleteBacktestRun).mockResolvedValue();
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([]);
    vi.mocked(getBacktestRun).mockResolvedValue(backtestRun());
    useMarketsStore().all = [eurUsdMarket];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads all run states, filters locally, shows disabled reasons, and selects through the overlay store', async () => {
    vi.mocked(listBacktestRuns).mockResolvedValue([
      backtestRun({
        run_id: 'run-succeeded-123456',
        status: 'succeeded',
        metrics: { total_return_pct: 1.25, trade_count: 3 },
      }),
      backtestRun({
        run_id: 'run-running-123456',
        status: 'running',
        completed_at_ms: null,
        metrics: null,
      }),
      backtestRun({
        run_id: 'run-failed-123456',
        status: 'failed',
        request: requestPayload({ symbols: ['GBPUSD'], timeframe: 'H1', strategyId: 'breakout' }),
        error_message: 'No candles available.',
      }),
      backtestRun({
        run_id: 'run-missing-market-123456',
        status: 'succeeded',
        request: requestPayload({ symbols: ['USDJPY'], timeframe: 'M5', strategyId: 'ema_cross' }),
      }),
      backtestRun({
        run_id: 'run-queued-123456',
        status: 'queued',
        completed_at_ms: null,
        request: requestPayload({ symbols: ['AUDUSD'], timeframe: 'M1', strategyId: 'mean_reversion' }),
        result_schema_version: null,
      }),
    ]);

    const wrapper = mountModal();
    await flushPromises();

    expect(listBacktestRuns).toHaveBeenCalledOnce();
    expect(wrapper.findAll('.backtest-run-row')).toHaveLength(5);
    expect(wrapper.text()).toContain('succeeded');
    expect(wrapper.text()).toContain('running');
    expect(wrapper.text()).toContain('failed');
    expect(wrapper.text()).toContain('queued');
    expect(wrapper.text()).toContain('sma_crossover');
    expect(wrapper.text()).toContain('EURUSD');
    expect(wrapper.text()).toContain('FX');
    expect(wrapper.text()).toContain('M15');
    expect(wrapper.text()).toContain('Submitted');
    expect(wrapper.text()).toContain('Completed');
    expect(wrapper.text()).toContain('total_return_pct 1.25');
    expect(wrapper.text()).toContain('trade_count 3');
    expect(wrapper.text()).toContain('Only succeeded Backtest Runs can be opened.');
    expect(wrapper.text()).toContain('Market FX:USDJPY is not available in the chart market list.');
    expect(wrapper.text()).not.toMatch(/refresh/i);
    expect(wrapper.text()).not.toMatch(/run-(succeeded|running|failed|missing-market|queued)/);
    expect(wrapper.findAll('[data-testid^="backtest-run-select-"]')).toHaveLength(0);
    expect(wrapper.text()).not.toContain('Open');

    await wrapper.find('#backtest-run-search-input').setValue('breakout');
    expect(wrapper.findAll('.backtest-run-row')).toHaveLength(1);
    expect(wrapper.text()).toContain('GBPUSD');

    await wrapper.find('#backtest-run-search-input').setValue('');
    await wrapper.find('[data-testid="backtest-run-status-filter"]').setValue('queued');
    expect(wrapper.findAll('.backtest-run-row')).toHaveLength(1);
    expect(wrapper.text()).toContain('mean_reversion');
    expect(wrapper.text()).toContain('AUDUSD');

    await wrapper.find('[data-testid="backtest-run-status-filter"]').setValue('all');
    await wrapper.find('[data-testid="backtest-run-row-run-running-123456"]').trigger('click');
    expect(fetchBacktestClosedTrades).not.toHaveBeenCalled();

    await wrapper.find('[data-testid="backtest-run-row-run-succeeded-123456"]').trigger('click');
    await flushPromises();

    expect(fetchBacktestClosedTrades).toHaveBeenCalledWith('run-succeeded-123456');
  });

  it('deletes terminal runs, removes them from history, and clears a selected overlay', async () => {
    vi.mocked(listBacktestRuns).mockResolvedValue([
      backtestRun({ run_id: 'run-succeeded-123456', status: 'succeeded' }),
      backtestRun({
        run_id: 'run-running-123456',
        status: 'running',
        completed_at_ms: null,
        metrics: null,
      }),
    ]);
    const confirm = vi.fn(() => true);
    vi.stubGlobal('confirm', confirm);

    const wrapper = mountModal();
    await flushPromises();

    await wrapper.find('[data-testid="backtest-run-row-run-succeeded-123456"]').trigger('click');
    await flushPromises();
    expect(useBacktestOverlayStore().selectedRunId).toBe('run-succeeded-123456');
    vi.mocked(fetchBacktestClosedTrades).mockClear();

    await wrapper.find('[data-testid="backtest-run-delete-run-succeeded-123456"]').trigger('click');
    await flushPromises();

    expect(confirm).toHaveBeenCalledWith(
      expect.stringContaining('all trades and fills'),
    );
    expect(deleteBacktestRun).toHaveBeenCalledWith('run-succeeded-123456');
    expect(fetchBacktestClosedTrades).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="backtest-run-row-run-succeeded-123456"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="backtest-run-row-run-running-123456"]').exists()).toBe(
      true,
    );
    expect(
      wrapper.find('[data-testid="backtest-run-delete-run-running-123456"]').attributes('disabled'),
    ).toBeDefined();
    expect(useBacktestOverlayStore().selectedRunId).toBeNull();
    expect(localStorage.getItem(STORAGE_KEYS.SELECTED_BACKTEST_RUN)).toBeNull();
  });

  it('keeps a run visible and shows an error when deletion fails', async () => {
    vi.mocked(listBacktestRuns).mockResolvedValue([
      backtestRun({ run_id: 'run-failed-123456', status: 'failed' }),
    ]);
    vi.mocked(deleteBacktestRun).mockRejectedValue(
      new Error('Failed to delete backtest run: Conflict'),
    );
    vi.stubGlobal('confirm', vi.fn(() => true));

    const wrapper = mountModal();
    await flushPromises();

    await wrapper.find('[data-testid="backtest-run-delete-run-failed-123456"]').trigger('click');
    await flushPromises();

    expect(deleteBacktestRun).toHaveBeenCalledWith('run-failed-123456');
    expect(wrapper.find('[data-testid="backtest-run-row-run-failed-123456"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Failed to delete backtest run: Conflict');
  });

  it('surfaces client loading errors without hiding history controls', async () => {
    vi.mocked(listBacktestRuns).mockRejectedValue(new Error('API unavailable'));

    const wrapper = mountModal();
    await flushPromises();

    expect(wrapper.text()).toContain('API unavailable');
    expect(wrapper.find('[data-testid="backtest-run-search"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="backtest-run-status-filter"]').exists()).toBe(true);
  });
});

function mountModal() {
  return mount(BacktestRunHistoryModal, {
    global: {
      stubs: {
        BaseModal: BaseModalStub,
        NButton: NButtonStub,
        NIcon: true,
        NInput: NInputStub,
        NScrollbar: { template: '<div><slot /></div>' },
        SearchOutline: true,
        TrashOutline: true,
        'base-modal': BaseModalStub,
        'n-button': NButtonStub,
        'n-icon': true,
        'n-input': NInputStub,
        'n-scrollbar': { template: '<div><slot /></div>' },
        'search-outline': true,
        'trash-outline': true,
      },
    },
  });
}

function backtestRun(overrides: Partial<BacktestRun> = {}): BacktestRun {
  return {
    run_id: 'run-123',
    status: 'succeeded',
    submitted_at_ms: 1_780_921_805_123,
    started_at_ms: 1_780_921_900_000,
    completed_at_ms: 1_780_922_100_000,
    request_schema_version: 1,
    request: requestPayload(),
    result_schema_version: 2,
    metrics: { total_return_pct: 1.25, trade_count: 3 },
    diagnostics: { execution_duration_ms: 240_000 },
    error_code: null,
    error_message: null,
    ...overrides,
  };
}

function requestPayload(overrides: {
  strategyId?: string;
  symbols?: string[];
  timeframe?: string;
} = {}): BacktestRun['request'] {
  return {
    symbols: overrides.symbols ?? ['EURUSD'],
    exchange: 'FX',
    timeframe: overrides.timeframe ?? 'M15',
    start_ms: 1_714_521_600_000,
    end_ms: 1_714_608_000_000,
    engine: 'event_driven',
    data_granularity: 'bar',
    initial_capital: 10_000,
    strategy: {
      strategy_id: overrides.strategyId ?? 'sma_crossover',
      parameters: { fast_window: 10, slow_window: 20 },
    },
    execution: {
      signal_timing: 'close',
      fill_timing: 'next_open',
      price_source: 'open',
      allow_partial_fills: false,
      allow_short: false,
      trade_accounting_policy: 'average_cost',
      gap_policy: 'skip',
      intrabar_exit_policy: 'conservative',
      commission_bps: 1,
      slippage_bps: 0.5,
    },
    persist_result: true,
    run_metadata: null,
  };
}
