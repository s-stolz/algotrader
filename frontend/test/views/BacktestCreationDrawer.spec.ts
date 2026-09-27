import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { NDatePicker, NDataTable, NInput, NInputNumber, NSelect } from 'naive-ui';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  BacktestSubmissionError, fetchStrategyCatalog, fetchSweepCapabilities,
  previewParameterSweep, submitBacktestBatch, submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestBatch, SweepPreview, SweepPreviewCandidate, SweepPreviewRequest } from '@/types/backtesterContracts';
import { reuseBatch, reuseStandalone } from '@/views/backtestReuse';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/api/backtesterClient')>(),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
  submitBacktestBatch: vi.fn(),
  previewParameterSweep: vi.fn(),
  fetchSweepCapabilities: vi.fn(),
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
    vi.mocked(submitBacktestBatch).mockReset();
    vi.mocked(fetchSweepCapabilities).mockReset();
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({
      max_sweep_candidate_count: 1000, batch_acceptance_enabled: false,
    });
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('uses Naive calendars and converts selected dates to UTC midnight', async () => {
    const wrapper = openDrawer();
    await flushPromises();
    const pickers = wrapper.findAllComponents(NDatePicker);
    expect(pickers).toHaveLength(2);
    pickers[0].vm.$emit('update:formatted-value', '2026-03-29');
    pickers[1].vm.$emit('update:formatted-value', '2026-10-25');
    await wrapper.vm.$nextTick();
    expect(useBacktestWorkspaceStore().creationDraft?.start_ms).toBe(Date.UTC(2026, 2, 29));
    expect(useBacktestWorkspaceStore().creationDraft?.end_ms).toBe(Date.UTC(2026, 9, 25));
    wrapper.unmount();
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

  it('reviews a changed saved version and invalid choice before creating independent history', async () => {
    const saved = {
      run_id: 'saved-run', request_schema_version: 3, status: 'succeeded',
      submitted_at_ms: 1_714_608_000_000,
      request: { symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M15',
        start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000,
        engine: 'vectorized', data_granularity: 'bar', initial_capital: 20_000,
        strategy: { strategy_id: 'sma_crossover', strategy_version: 1,
          parameters: { enabled: true, fast_window: 4, label: 'b', stop_loss_pct: null } },
        execution: { signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
          allow_partial_fills: false, allowed_directions: 'long_and_short',
          trade_accounting_policy: 'average_cost', gap_policy: 'skip',
          intrabar_exit_policy: 'conservative', commission_bps: 0, slippage_bps: 0 },
        persist_result: false, run_metadata: null },
    } as Parameters<typeof reuseStandalone>[0];
    const original = structuredClone(saved);
    useBacktestWorkspaceStore().createFromSaved(reuseStandalone(saved));
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([{ ...catalog[0], strategy_version: 2,
      parameters: catalog[0].parameters.map((parameter) => parameter.name === 'label'
        ? { ...parameter, choices: ['a', 'c'], default: 'c' } : parameter) }]);
    vi.mocked(submitBacktestRun).mockResolvedValue('fresh-run');

    const wrapper = openDrawer();
    await flushPromises();
    expect(document.body.textContent).toContain('Saved sma_crossover version 1');
    expect(document.body.textContent).toContain('current version 2');
    expect(document.body.textContent).toContain('Invalid copied value: label');
    expect(document.body.textContent).toContain('fast_window: saved value 4; current default 5');
    expect((document.querySelector('[data-testid="creation-submit"]') as HTMLButtonElement).disabled).toBe(true);

    (document.querySelector('[data-testid="reuse-use-current"]') as HTMLElement).click();
    await flushPromises();
    (document.querySelector('[data-testid="creation-submit"]') as HTMLElement).click();
    await flushPromises();
    expect(submitBacktestRun).not.toHaveBeenCalled();
    const label = wrapper.findAllComponents(NSelect).find((select) =>
      select.attributes('data-testid') === 'creation-param-label');
    label!.vm.$emit('update:value', 1);
    await flushPromises();
    (document.querySelector('[data-testid="creation-submit"]') as HTMLElement).click();
    await flushPromises();
    expect(submitBacktestRun).toHaveBeenCalledWith(expect.objectContaining({
      strategy: expect.objectContaining({ strategy_version: 2,
        parameters: expect.objectContaining({ label: 'c', fast_window: 4 }) }),
    }));
    expect(wrapper.emitted('submitted')?.[0]).toEqual(['fresh-run']);
    expect(saved).toEqual(original);
    wrapper.unmount();
  });

  it('keeps a removed saved strategy inspectable and unavailable for reuse', async () => {
    const saved = { run_id: 'removed', request_schema_version: 2,
      request: { symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M1',
        start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000,
        engine: 'vectorized', data_granularity: 'bar', initial_capital: 10_000,
        strategy: { strategy_id: 'retired', parameters: {} },
        execution: { signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
          allow_partial_fills: false, allowed_directions: 'long_and_short',
          trade_accounting_policy: 'average_cost', gap_policy: 'skip',
          intrabar_exit_policy: 'conservative', commission_bps: 0, slippage_bps: 0 },
        persist_result: false, run_metadata: null } } as
      Parameters<typeof reuseStandalone>[0];
    useBacktestWorkspaceStore().createFromSaved(reuseStandalone(saved));
    const wrapper = openDrawer();
    await flushPromises();
    expect(document.querySelector('[data-testid="reuse-removed-strategy"]')?.textContent)
      .toContain('no longer registered');
    expect((document.querySelector('[data-testid="creation-submit"]') as HTMLButtonElement).disabled).toBe(true);
    expect(submitBacktestRun).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});

const sweepCatalog = [{
  strategy_id: 'sma_crossover', strategy_version: 1, display_name: 'SMA crossover',
  parameters: [{ name: 'fast_window', type: 'int' as const, required: false, nullable: false,
    default: 5 }],
}];

function previewFor(request: SweepPreviewRequest, count: number): SweepPreview {
  const market = { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' };
  return {
    max_sweep_candidate_count: 1000,
    normalized_selections: { markets: [market], timeframes: ['M1'],
      parameters: { fast_window: { mode: 'constant', values: [5] } },
      allowed_directions: ['long_and_short'] },
    raw_count: count, ready_count: count, excluded_count: 0,
    candidates: Array.from({ length: count }, (_, candidate_ordinal) => ({
      candidate_ordinal, market, timeframe: 'M1', parameters: { fast_window: 5 },
      allowed_directions: 'long_and_short', status: 'ready', member_ordinal: candidate_ordinal,
      request: { ...request, symbols: ['EURUSD'], exchange: 'FX', timeframe: 'M1',
        strategy: { ...request.strategy, parameters: { fast_window: 5 } } },
    })),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function advancePreview() {
  await vi.advanceTimersByTimeAsync(170);
  await flushPromises();
}

describe('Parameter Sweep creation review', () => {
  let pinia: ReturnType<typeof createPinia>;

  beforeEach(() => {
    vi.useFakeTimers();
    pinia = createPinia();
    setActivePinia(pinia);
    useMarketsStore().all = [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX',
      market_type: 'Forex', min_move: 0.00001, timezone: 'UTC' }];
    useBacktestWorkspaceStore().creationSweepDraft = {
      isSweep: true, marketIds: [1], timeframes: ['M1'],
      allowedDirections: ['long_and_short'], parameters: {},
    };
    vi.mocked(fetchStrategyCatalog).mockReset();
    vi.mocked(fetchStrategyCatalog).mockResolvedValue(sweepCatalog);
    vi.mocked(previewParameterSweep).mockReset();
    vi.mocked(fetchSweepCapabilities).mockReset();
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({
      max_sweep_candidate_count: 1000, batch_acceptance_enabled: false,
    });
    vi.mocked(submitBacktestRun).mockReset();
    vi.mocked(submitBacktestBatch).mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    vi.useRealTimers();
  });

  it('revalidates a saved range batch against current defaults and Markets with a fresh identity', async () => {
    const batch = {
      batch_id: 'saved-batch', submission_id: 'old-submission', strategy_id: 'sma_crossover',
      strategy_version: 1,
      accepted_definition: { shared_request: {
        symbols: [], exchange: null, timeframe: 'M1',
        start_ms: 1_714_521_600_000, end_ms: 1_714_608_000_000,
        engine: 'vectorized', data_granularity: 'bar', initial_capital: 10_000,
        strategy: { strategy_id: 'sma_crossover', strategy_version: 1, parameters: {} },
        execution: { signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
          allow_partial_fills: false, allowed_directions: 'long_and_short',
          trade_accounting_policy: 'average_cost', gap_policy: 'skip',
          intrabar_exit_policy: 'conservative', commission_bps: 0, slippage_bps: 0 },
        persist_result: false, run_metadata: null,
      }, normalized_selections: { markets: [{ symbol_id: 9, symbol: 'GONE', exchange: 'FX' },
        { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
      timeframes: ['H1', 'M1'], allowed_directions: ['short_only', 'long_and_short'],
      parameters: { fast_window: { mode: 'range', values: [3, 5],
        range: { start: 3, stop: 5, step: 2 } },
      slow_window: { mode: 'default', values: [20] } } } },
      strategy_metadata: { strategy_id: 'sma_crossover', strategy_version: 1,
        display_name: 'SMA', parameters: [
          { name: 'fast_window', type: 'int', required: false, nullable: false, default: 3 },
          { name: 'slow_window', type: 'int', required: false, nullable: false, default: 20 },
        ] },
    } as unknown as BacktestBatch;
    const original = structuredClone(batch);
    useBacktestWorkspaceStore().createFromSaved(reuseBatch(batch));
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([{ ...sweepCatalog[0], strategy_version: 2,
      parameters: [...sweepCatalog[0].parameters,
        { name: 'slow_window', type: 'int', required: false, nullable: false, default: 30 }] }]);
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({ max_sweep_candidate_count: 1000,
      batch_acceptance_enabled: true });
    vi.mocked(previewParameterSweep).mockRejectedValueOnce(new Error(
      'Raw candidate count exceeds current limit',
    )).mockImplementation(async (request) => {
      const result = previewFor(request, 2);
      result.candidates[1] = { ...result.candidates[1], status: 'excluded',
        issues: [{ code: 'invalid_parameter_combination', fields: ['fast_window'],
          message: 'Current validator excludes this combination' }] };
      delete result.candidates[1].request;
      delete result.candidates[1].member_ordinal;
      result.ready_count = 1;
      result.excluded_count = 1;
      return result;
    });
    vi.mocked(submitBacktestBatch).mockResolvedValue('fresh-batch');
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
    });
    await advancePreview();
    expect(document.body.textContent).toContain('Saved sma_crossover version 1');
    expect(document.body.textContent).toContain('slow_window default changed: 20 → 30');
    expect(document.body.textContent).toContain('Saved Market ID 9 unavailable');
    expect(previewParameterSweep).not.toHaveBeenCalled();

    (document.querySelector('[data-testid="reuse-use-current"]') as HTMLElement).click();
    await flushPromises();
    const market = wrapper.findAllComponents(NSelect).find((select) =>
      select.attributes('data-testid') === 'sweep-markets');
    market!.vm.$emit('update:value', [1]);
    await advancePreview();
    expect(document.body.textContent).toContain('Raw candidate count exceeds current limit');
    expect(submitBacktestBatch).not.toHaveBeenCalled();
    const capital = wrapper.findAllComponents(NInputNumber).find((input) =>
      input.attributes('data-testid') === 'creation-capital');
    capital!.vm.$emit('update:value', 12_000);
    await advancePreview();
    expect(previewParameterSweep).toHaveBeenCalledWith(expect.objectContaining({
      markets: [1], timeframes: ['H1', 'M1'], allowed_directions: ['short_only', 'long_and_short'],
      strategy: { strategy_id: 'sma_crossover', strategy_version: 2 },
      parameter_axes: { fast_window: { mode: 'range', start: 3, stop: 5, step: 2 },
        slow_window: { mode: 'constant', value: 30 } },
    }));
    expect(document.body.textContent).toContain('1 Excluded');
    (document.querySelector('[data-testid="sweep-submit"]') as HTMLElement).click();
    await flushPromises();
    expect(submitBacktestBatch).toHaveBeenCalledWith(expect.anything(),
      expect.not.stringContaining('old-submission'));
    expect(wrapper.emitted('submitted-batch')?.[0]).toEqual(['fresh-batch']);
    expect(batch).toEqual(original);
    wrapper.unmount();
  });

  it('uses one submission identity for a reviewed batch retry', async () => {
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({
      max_sweep_candidate_count: 1000, batch_acceptance_enabled: true,
    });
    vi.mocked(previewParameterSweep).mockImplementation(async (request) => previewFor(request, 2));
    vi.mocked(submitBacktestBatch)
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValueOnce('batch-1');
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
    });
    await advancePreview();
    const submit = document.querySelector('[data-testid="sweep-submit"]') as HTMLElement;
    expect(submit).not.toBeNull();
    submit.click();
    await flushPromises();
    expect(submitBacktestBatch).toHaveBeenCalledTimes(1);
    expect(document.body.textContent).toContain('Connection lost');
    await advancePreview();
    submit.click();
    await flushPromises();
    expect(submitBacktestBatch).toHaveBeenCalledTimes(2);
    expect(vi.mocked(submitBacktestBatch).mock.calls[0][1]).toBe(
      vi.mocked(submitBacktestBatch).mock.calls[1][1]);
    expect(wrapper.emitted('submitted-batch')?.[0]).toEqual(['batch-1']);
    wrapper.unmount();
  });

  it('keeps parameter input modes and sends independent range inputs', async () => {
    vi.mocked(previewParameterSweep).mockImplementation(async (request) => previewFor(request, 2));
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
    });
    await flushPromises();
    const mode = wrapper.findAllComponents(NSelect).find((select) =>
      select.attributes('data-testid') === 'sweep-mode-fast_window');
    mode!.vm.$emit('update:value', 'range');
    await flushPromises();
    const inputs = wrapper.findAllComponents(NInputNumber);
    const range = inputs.filter((input) => input.attributes('data-testid') === undefined);
    range[0].vm.$emit('update:value', 1);
    range[1].vm.$emit('update:value', 3);
    range[2].vm.$emit('update:value', 1);
    await advancePreview();
    expect(document.body.textContent).toContain('Current raw candidate limit: 1000');
    expect(previewParameterSweep).toHaveBeenCalledWith(expect.objectContaining({
      markets: [1], timeframes: ['M1'], parameter_axes: {
        fast_window: { mode: 'range', start: 1, stop: 3, step: 1 },
      },
    }));
    expect(document.body.textContent).toContain('2 raw candidates');
    expect(submitBacktestRun).not.toHaveBeenCalled();
    mode!.vm.$emit('update:value', 'constant');
    await flushPromises();
    expect(document.body.querySelector('[data-testid="creation-param-fast_window"]')).not.toBeNull();
    expect(useBacktestWorkspaceStore().creationSweepDraft?.parameters.fast_window.rangeStop).toBe(3);
    wrapper.unmount();
  });

  it('previews exact string values including empty, multiline, and whitespace strings', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([{
      ...sweepCatalog[0], parameters: [{ name: 'label', type: 'str', required: false,
        nullable: false, default: 'default' }],
    }]);
    vi.mocked(previewParameterSweep).mockImplementation(async (request) => previewFor(request, 1));
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
    });
    await flushPromises();
    const mode = wrapper.findAllComponents(NSelect).find((select) =>
      select.attributes('data-testid') === 'sweep-mode-label');
    mode!.vm.$emit('update:value', 'values');
    await advancePreview();
    expect(document.body.textContent).toContain('Select at least one value for label.');

    (document.querySelector('[data-testid="sweep-add-label"]') as HTMLElement).click();
    await advancePreview();
    expect(vi.mocked(previewParameterSweep).mock.lastCall?.[0].parameter_axes.label).toEqual({
      mode: 'values', values: [''],
    });

    (document.querySelector('[data-testid="sweep-add-label"]') as HTMLElement).click();
    await flushPromises();
    const multiline = wrapper.findAllComponents(NInput).find((input) =>
      input.attributes('data-testid') === 'sweep-string-label-1');
    multiline!.vm.$emit('update:value', 'first\nsecond');
    (document.querySelector('[data-testid="sweep-add-label"]') as HTMLElement).click();
    await flushPromises();
    const whitespace = wrapper.findAllComponents(NInput).find((input) =>
      input.attributes('data-testid') === 'sweep-string-label-2');
    whitespace!.vm.$emit('update:value', ' ');
    await advancePreview();
    expect(vi.mocked(previewParameterSweep).mock.lastCall?.[0].parameter_axes.label).toEqual({
      mode: 'values', values: ['', 'first\nsecond', ' '],
    });
    expect(useBacktestWorkspaceStore().creationSweepDraft?.parameters.label.stringValues)
      .toEqual(['', 'first\nsecond', ' ']);

    (document.querySelector('[data-testid="sweep-remove-label-0"]') as HTMLElement).click();
    await advancePreview();
    expect(vi.mocked(previewParameterSweep).mock.lastCall?.[0].parameter_axes.label).toEqual({
      mode: 'values', values: ['first\nsecond', ' '],
    });
    wrapper.unmount();
  });

  it('ignores an old preview after a newer draft revision succeeds', async () => {
    const first = deferred<SweepPreview>();
    const second = deferred<SweepPreview>();
    vi.mocked(previewParameterSweep).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
    });
    await flushPromises();
    await advancePreview();
    expect(previewParameterSweep).toHaveBeenCalledTimes(1);
    const capital = wrapper.findAllComponents(NInputNumber).find((input) =>
      input.attributes('data-testid') === 'creation-capital');
    capital!.vm.$emit('update:value', 20_000);
    await advancePreview();
    expect(previewParameterSweep).toHaveBeenCalledTimes(2);
    const newRequest = vi.mocked(previewParameterSweep).mock.calls[1][0];
    second.resolve(previewFor(newRequest, 2));
    await flushPromises();
    first.resolve(previewFor(vi.mocked(previewParameterSweep).mock.calls[0][0], 1));
    await flushPromises();
    expect(document.body.textContent).toContain('2 raw candidates');
    expect(document.body.textContent).not.toContain('1 raw candidates');
    wrapper.unmount();
  });

  it('reviews all candidates with local paging, filtering, and ordinal sort ties', async () => {
    vi.mocked(previewParameterSweep).mockImplementation(async (request) => {
      const result = previewFor(request, 22);
      result.candidates[1] = { ...result.candidates[1], status: 'excluded',
        issues: [{ code: 'invalid_parameter_combination', fields: ['fast_window'],
          message: 'Excluded combination' }] };
      delete result.candidates[1].request;
      delete result.candidates[1].member_ordinal;
      for (let index = 2; index < result.candidates.length; index += 1) {
        result.candidates[index].member_ordinal = index - 1;
      }
      result.ready_count = 21;
      result.excluded_count = 1;
      return result;
    });
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
    });
    await flushPromises();
    await advancePreview();
    const table = wrapper.findComponent(NDataTable);
    const rows = table.props('data') as SweepPreviewCandidate[];
    expect(rows).toHaveLength(22);
    expect(table.props('pagination')).toEqual({ pageSize: 20 });
    const columns = table.props('columns') as Array<{ title: string; sorter?: (a: unknown, b: unknown) => number }>;
    expect(columns.map((column) => column.title)).toEqual([
      'Candidate #', 'Market', 'Timeframe', 'fast_window', 'Allowed Directions', 'State',
    ]);
    expect(columns[3]!.sorter!(rows[0]!, rows[2]!)).toBeLessThan(0);
    const filter = wrapper.findAllComponents(NSelect).find((select) =>
      select.attributes('data-testid') === 'sweep-filter');
    filter!.vm.$emit('update:value', 'excluded');
    await flushPromises();
    const excludedRows = table.props('data') as SweepPreviewCandidate[];
    expect(excludedRows).toHaveLength(1);
    expect(excludedRows[0]!.issues?.[0]?.message).toBe('Excluded combination');
    filter!.vm.$emit('update:value', 'ready');
    await flushPromises();
    expect(table.props('data')).toHaveLength(21);
    wrapper.unmount();
  });

  it('refreshes changed catalog metadata without submitting or accepting stale preview', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValueOnce(sweepCatalog).mockResolvedValueOnce([{
      ...sweepCatalog[0], strategy_version: 2,
    }]);
    vi.mocked(previewParameterSweep).mockRejectedValueOnce(new BacktestSubmissionError(
      'strategy_version_unavailable', [], 'Strategy version is unavailable',
    )).mockImplementation(async (request) => previewFor(request, 1));
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true }, global: { plugins: [pinia] }, attachTo: document.body,
    });
    await flushPromises();
    await advancePreview();
    expect(fetchStrategyCatalog).toHaveBeenCalledTimes(2);
    expect(document.body.textContent).toContain('Strategy version changed');
    expect(document.body.querySelector('[data-testid="sweep-review"]')).toBeNull();
    expect(previewParameterSweep).toHaveBeenCalledTimes(1);
    const button = [...document.body.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Use current version'));
    button!.click();
    await advancePreview();
    expect(previewParameterSweep).toHaveBeenCalledTimes(2);
    expect(document.body.querySelector('[data-testid="sweep-review"]')).not.toBeNull();
    expect(submitBacktestRun).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
