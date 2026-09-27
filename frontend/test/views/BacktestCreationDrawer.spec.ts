import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { NSelect } from 'naive-ui';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  BacktestSubmissionError, fetchStrategyCatalog, submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/backtesterClient')>(),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
}));

const catalog = [{
  strategy_id: 'sma_crossover', strategy_version: 1, display_name: 'SMA crossover',
  parameters: [
    { name: 'enabled', type: 'bool' as const, required: false, nullable: false, default: true },
    { name: 'fast_window', type: 'int' as const, required: false, nullable: false, default: 5 },
    { name: 'label', type: 'str' as const, required: false, nullable: false, default: 'a',
      choices: ['a', 'b'] },
    { name: 'stop_loss_pct', type: 'float' as const, required: false, nullable: true,
      default: null },
  ],
}];

let pinia: ReturnType<typeof createPinia>;

function openDrawer() {
  return mount(BacktestCreationDrawer, {
    props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
  });
}

describe('standalone creation drawer', () => {
  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);
    useMarketsStore().all = [{
      symbol_id: 1, symbol: 'EURUSD', exchange: 'FX', market_type: 'Forex',
      min_move: 0.00001, timezone: 'UTC',
    }];
    vi.mocked(fetchStrategyCatalog).mockReset();
    vi.mocked(fetchStrategyCatalog).mockResolvedValue(catalog);
    vi.mocked(submitBacktestRun).mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('renders catalog types and submits a retained exact-version draft', async () => {
    const store = useBacktestWorkspaceStore();
    store.creationDraft = {
      symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M15',
      start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000,
      engine: 'event_driven', data_granularity: 'bar', initial_capital: 25_000,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1,
        parameters: { enabled: true, fast_window: 3, label: 'b', stop_loss_pct: null } },
      execution: {
        signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
        allow_partial_fills: false, allowed_directions: 'short_only',
        trade_accounting_policy: 'average_cost', gap_policy: 'skip',
        intrabar_exit_policy: 'conservative', commission_bps: 0, slippage_bps: 0,
      },
      persist_result: false,
    };
    vi.mocked(submitBacktestRun).mockResolvedValue('run-new');

    const wrapper = openDrawer();
    await flushPromises();
    expect(document.body.textContent).toContain('Version 1');
    expect(document.querySelector('[data-testid="creation-param-enabled"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="creation-param-fast_window"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="creation-param-label"]')).not.toBeNull();

    (document.querySelector('[data-testid="creation-submit"]') as HTMLElement).click();
    await flushPromises();

    expect(submitBacktestRun).toHaveBeenCalledWith(expect.objectContaining({
      timeframe: 'M15', initial_capital: 25_000,
      strategy: { strategy_id: 'sma_crossover', strategy_version: 1,
        parameters: { enabled: true, fast_window: 3, label: 'b', stop_loss_pct: null } },
      execution: expect.objectContaining({ allowed_directions: 'short_only' }),
    }));
    expect(wrapper.emitted('submitted')?.[0]).toEqual(['run-new']);
    wrapper.unmount();
  });

  it('refreshes stale catalog and leaves the draft unchanged without retrying submission', async () => {
    vi.mocked(submitBacktestRun).mockRejectedValue(new BacktestSubmissionError(
      'strategy_version_unavailable', [], 'Strategy version is unavailable',
    ));
    const wrapper = openDrawer();
    await flushPromises();

    (document.querySelector('[data-testid="creation-submit"]') as HTMLElement).click();
    await flushPromises();

    expect(submitBacktestRun).toHaveBeenCalledTimes(1);
    expect(fetchStrategyCatalog).toHaveBeenCalledTimes(2);
    expect(useBacktestWorkspaceStore().creationDraft?.strategy.strategy_version).toBe(1);
    expect(document.body.textContent).toContain('Review the refreshed catalog');
    wrapper.unmount();
  });

  it('keeps a restricted string that resembles null distinct from explicit null', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([{
      ...catalog[0],
      parameters: [{ name: 'label', type: 'str', required: false, nullable: true,
        default: '__null__', choices: ['__null__', 'other'] }],
    }]);
    vi.mocked(submitBacktestRun).mockResolvedValue('run-choice');
    const wrapper = openDrawer();
    await flushPromises();

    const labelSelect = wrapper.findAllComponents(NSelect).find((select) =>
      select.attributes('data-testid') === 'creation-param-label');
    expect(labelSelect).toBeDefined();
    expect(labelSelect!.props('value')).toBe(0);
    expect(labelSelect!.props('options')).toEqual([
      { label: '__null__', value: 0 },
      { label: 'other', value: 1 },
      { label: 'Null', value: 2 },
    ]);

    (document.querySelector('[data-testid="creation-submit"]') as HTMLElement).click();
    await flushPromises();
    expect(vi.mocked(submitBacktestRun).mock.calls[0][0].strategy.parameters.label).toBe('__null__');

    labelSelect!.vm.$emit('update:value', 2);
    await flushPromises();
    (document.querySelector('[data-testid="creation-submit"]') as HTMLElement).click();
    await flushPromises();
    expect(vi.mocked(submitBacktestRun).mock.calls[1][0].strategy.parameters.label).toBeNull();
    wrapper.unmount();
  });

  it('shows a required parameter error without submitting an incomplete draft', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([{
      ...catalog[0],
      parameters: [{ name: 'threshold', type: 'int', required: true, nullable: false }],
    }]);
    const wrapper = openDrawer();
    await flushPromises();

    (document.querySelector('[data-testid="creation-submit"]') as HTMLElement).click();
    await flushPromises();

    expect(document.body.textContent).toContain('This parameter is required.');
    expect(submitBacktestRun).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
