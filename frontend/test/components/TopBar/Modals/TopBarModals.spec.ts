import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fetchBacktestClosedTrades,
  getBacktestRun,
  listBacktestRuns,
} from '@/api/backtesterClient';
import { useModalStore } from '@/stores/modalStore';
import type { BacktestRun } from '@/types/backtesterContracts';
import type { Market } from '@/types/contracts';

import TopBarModals from '@/components/TopBar/Modals/TopBarModals.vue';

vi.mock('@/api/backtesterClient', () => ({
  fetchBacktestClosedTrades: vi.fn(),
  getBacktestRun: vi.fn(),
  listBacktestRuns: vi.fn(),
}));

const market: Market = {
  symbol_id: 1,
  symbol: 'EURUSD',
  exchange: 'FX',
  market_type: 'Forex',
  min_move: 0.00001,
  timezone: 'UTC',
};

const updateCurrentMarket = vi.fn();

const SymbolSearchModalStub = defineComponent({
  name: 'SymbolSearchModal',
  emits: ['open-symbol-form-modal', 'remove-market', 'upload-data'],
  setup(_, { emit, expose }) {
    expose({ updateCurrentMarket });
    return () => h('div', [
      h('button', {
        class: 'open-symbol-form',
        onClick: () => emit('open-symbol-form-modal'),
      }, 'Add'),
      h('button', {
        class: 'remove-market',
        onClick: () => emit('remove-market', market),
      }, 'Remove'),
      h('button', {
        class: 'upload-data',
        onClick: () => emit('upload-data', market),
      }, 'Upload'),
    ]);
  },
});

const RemoveMarketModalStub = defineComponent({
  name: 'RemoveMarketModal',
  emits: ['market-removed'],
  setup(_, { emit }) {
    return () => h('button', {
      class: 'market-removed',
      onClick: () => emit('market-removed', market),
    }, 'Removed');
  },
});

const UploadDataModalStub = defineComponent({
  name: 'UploadDataModal',
  emits: ['upload-successful'],
  setup(_, { emit }) {
    return () => h('button', {
      class: 'upload-successful',
      onClick: () => emit('upload-successful', market),
    }, 'Uploaded');
  },
});

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
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      onClick: () => emit('click'),
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
    inputProps: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      ...props.inputProps,
      value: props.value,
      onInput: (event: Event) => {
        emit('update:value', (event.target as HTMLInputElement).value);
      },
    });
  },
});

describe('TopBarModals', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    updateCurrentMarket.mockReset();
    vi.mocked(fetchBacktestClosedTrades).mockReset();
    vi.mocked(getBacktestRun).mockReset();
    vi.mocked(listBacktestRuns).mockReset();
    vi.mocked(fetchBacktestClosedTrades).mockResolvedValue([]);
    vi.mocked(getBacktestRun).mockResolvedValue(backtestRun());
    vi.mocked(listBacktestRuns).mockResolvedValue([]);
  });

  it('coordinates market modal events with kebab-case contracts', async () => {
    const modalStore = useModalStore();
    const wrapper = mount(TopBarModals, {
      global: {
        stubs: {
          IndicatorSearchModal: true,
          RemoveMarketModal: RemoveMarketModalStub,
          SymbolFormModal: true,
          SymbolSearchModal: SymbolSearchModalStub,
          UploadDataModal: UploadDataModalStub,
          'indicator-search-modal': true,
          'remove-market-modal': RemoveMarketModalStub,
          'symbol-form-modal': true,
          'symbol-search-modal': SymbolSearchModalStub,
          'upload-data-modal': UploadDataModalStub,
        },
      },
    });

    await wrapper.find('.open-symbol-form').trigger('click');
    expect(modalStore.activeModal).toBe('symbolForm');

    await wrapper.find('.remove-market').trigger('click');
    expect(modalStore.activeModal).toBe('removeMarket');
    await wrapper.find('.market-removed').trigger('click');
    expect(updateCurrentMarket).toHaveBeenCalledWith(market);

    await wrapper.find('.upload-data').trigger('click');
    expect(modalStore.activeModal).toBe('uploadData');
    await wrapper.find('.upload-successful').trigger('click');
    expect(updateCurrentMarket).toHaveBeenCalledWith(market);
  });

  it('refetches Backtest Runs when the history modal is closed and reopened', async () => {
    const modalStore = useModalStore();
    const wrapper = mount(TopBarModals, {
      global: {
        stubs: {
          BaseModal: BaseModalStub,
          IndicatorSearchModal: true,
          NButton: NButtonStub,
          NIcon: true,
          NInput: NInputStub,
          NScrollbar: { template: '<div><slot /></div>' },
          RemoveMarketModal: true,
          SearchOutline: true,
          SymbolFormModal: true,
          SymbolSearchModal: true,
          UploadDataModal: true,
          'base-modal': BaseModalStub,
          'indicator-search-modal': true,
          'n-button': NButtonStub,
          'n-icon': true,
          'n-input': NInputStub,
          'n-scrollbar': { template: '<div><slot /></div>' },
          'remove-market-modal': true,
          'search-outline': true,
          'symbol-form-modal': true,
          'symbol-search-modal': true,
          'upload-data-modal': true,
        },
      },
    });

    modalStore.openModal('backtestRuns');
    await flushPromises();

    expect(listBacktestRuns).toHaveBeenCalledOnce();

    modalStore.closeModal();
    await flushPromises();

    expect(wrapper.findComponent({ name: 'BacktestRunHistoryModal' }).exists()).toBe(false);

    modalStore.openModal('backtestRuns');
    await flushPromises();

    expect(listBacktestRuns).toHaveBeenCalledTimes(2);
  });
});

function backtestRun(overrides: Partial<BacktestRun> = {}): BacktestRun {
  return {
    run_id: 'run-123',
    status: 'succeeded',
    submitted_at_ms: 1_780_921_805_123,
    started_at_ms: 1_780_921_900_000,
    completed_at_ms: 1_780_922_100_000,
    request_schema_version: 1,
    request: {
      symbols: ['EURUSD'],
      exchange: 'FX',
      timeframe: 'M15',
      start_ms: 1_714_521_600_000,
      end_ms: 1_714_608_000_000,
      engine: 'event_driven',
      data_granularity: 'bar',
      initial_capital: 10_000,
      strategy: {
        strategy_id: 'sma_crossover',
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
    },
    result_schema_version: 2,
    metrics: { total_return_pct: 1.25, trade_count: 3 },
    diagnostics: { execution_duration_ms: 240_000 },
    error_code: null,
    error_message: null,
    ...overrides,
  };
}
