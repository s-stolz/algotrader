import { flushPromises } from '@vue/test-utils';
import { NDatePicker, NInput, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { catalog, openDrawer, standaloneSetup } from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
  submitBacktestBatch: vi.fn(),
  previewParameterSweep: vi.fn(),
  fetchSweepCapabilities: vi.fn(),
}));

describe('standalone', () => {
  standaloneSetup();

  it(
    'starts with an empty optional name, preserves drafts, and ' +
      'normalizes named and unnamed submissions',
    async () => {
      vi.mocked(submitBacktestRun).mockResolvedValue('run-name');
      let wrapper = openDrawer();
      await flushPromises();
      const input = () =>
        wrapper
          .findAllComponents(NInput)
          .find(
            (component) =>
              component.attributes('data-testid') === 'creation-name',
          )!;
      expect(input().props('value')).toBe('');
      expect(input().props('placeholder')).toBe('Enter an experiment name');
      input().vm.$emit('update:value', '  Research baseline  ');
      await flushPromises();
      wrapper.unmount();
      wrapper = openDrawer();
      await flushPromises();
      expect(input().props('value')).toBe('  Research baseline  ');
      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktestRun).toHaveBeenLastCalledWith(
        expect.objectContaining({ name: 'Research baseline' }),
      );
      expect(
        vi.mocked(submitBacktestRun).mock.calls[0][0].run_metadata,
      ).toBeNull();
      input().vm.$emit('update:value', '   ');
      await flushPromises();
      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktestRun).toHaveBeenLastCalledWith(
        expect.objectContaining({ name: null }),
      );
      for (const name of ['a'.repeat(121), 'two\nlines', '\ntrimmed']) {
        input().vm.$emit('update:value', name);
        await flushPromises();
        (
          document.querySelector(
            '[data-testid="creation-submit"]',
          ) as HTMLElement
        ).click();
        await flushPromises();
        expect(submitBacktestRun).toHaveBeenCalledTimes(2);
        expect(document.body.textContent).toContain('Experiment name must');
      }
      wrapper.unmount();
    },
  );

  it('uses Naive calendars and converts selected dates to UTC midnight', async () => {
    const wrapper = openDrawer();
    await flushPromises();
    const pickers = wrapper.findAllComponents(NDatePicker);
    expect(pickers).toHaveLength(2);
    pickers[0].vm.$emit('update:formatted-value', '2026-03-29');
    pickers[1].vm.$emit('update:formatted-value', '2026-10-25');
    await wrapper.vm.$nextTick();
    expect(useBacktestWorkspaceStore().creationDraft?.start_ms).toBe(
      Date.UTC(2026, 2, 29),
    );
    expect(useBacktestWorkspaceStore().creationDraft?.end_ms).toBe(
      Date.UTC(2026, 9, 25),
    );
    wrapper.unmount();
  });

  it('renders catalog types and submits a retained exact-version draft', async () => {
    const store = useBacktestWorkspaceStore();
    store.creationDraft = {
      symbols: ['EURUSD'],
      exchange: 'FX',
      timeframe: 'M15',
      start_ms: 1_714_521_600_000,
      end_ms: 1_714_608_000_000,
      engine: 'event_driven',
      data_granularity: 'bar',
      initial_capital: 25_000,
      strategy: {
        strategy_id: 'sma_crossover',
        strategy_version: 1,
        parameters: {
          enabled: true,
          fast_window: 3,
          label: 'b',
          stop_loss_pct: null,
        },
      },
      execution: {
        signal_timing: 'close',
        fill_timing: 'next_open',
        price_source: 'open',
        allow_partial_fills: false,
        allowed_directions: 'short_only',
        trade_accounting_policy: 'average_cost',
        gap_policy: 'skip',
        intrabar_exit_policy: 'conservative',
        commission_bps: 0,
        slippage_bps: 0,
      },
      persist_result: false,
    };
    vi.mocked(submitBacktestRun).mockResolvedValue('run-new');

    const wrapper = openDrawer();
    await flushPromises();
    expect(document.body.textContent).toContain('Version 1');
    expect(
      document.querySelector('[data-testid="creation-param-enabled"]'),
    ).not.toBeNull();
    expect(
      document.querySelector('[data-testid="creation-param-fast_window"]'),
    ).not.toBeNull();
    expect(
      document.querySelector('[data-testid="creation-param-label"]'),
    ).not.toBeNull();

    (
      document.querySelector('[data-testid="creation-submit"]') as HTMLElement
    ).click();
    await flushPromises();

    expect(submitBacktestRun).toHaveBeenCalledWith(
      expect.objectContaining({
        timeframe: 'M15',
        initial_capital: 25_000,
        strategy: {
          strategy_id: 'sma_crossover',
          strategy_version: 1,
          parameters: {
            enabled: true,
            fast_window: 3,
            label: 'b',
            stop_loss_pct: null,
          },
        },
        execution: expect.objectContaining({
          allowed_directions: 'short_only',
        }),
      }),
    );
    expect(wrapper.emitted('submitted')?.[0]).toEqual(['run-new']);
    wrapper.unmount();
  });

  it(
    'refreshes stale catalog and leaves the draft unchanged without ' +
      'retrying submission',
    async () => {
      vi.mocked(submitBacktestRun).mockRejectedValue(
        new BacktestSubmissionError(
          'strategy_version_unavailable',
          [],
          'Strategy version is unavailable',
        ),
      );
      const wrapper = openDrawer();
      await flushPromises();

      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();

      expect(submitBacktestRun).toHaveBeenCalledTimes(1);
      expect(fetchStrategyCatalog).toHaveBeenCalledTimes(2);
      expect(
        useBacktestWorkspaceStore().creationDraft?.strategy.strategy_version,
      ).toBe(1);
      expect(document.body.textContent).toContain(
        'Review the refreshed catalog',
      );
      wrapper.unmount();
    },
  );

  it('keeps a restricted string that resembles null distinct from explicit null', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([
      {
        ...catalog[0],
        parameters: [
          {
            name: 'label',
            type: 'str',
            required: false,
            nullable: true,
            default: '__null__',
            choices: ['__null__', 'other'],
          },
        ],
      },
    ]);
    vi.mocked(submitBacktestRun).mockResolvedValue('run-choice');
    const wrapper = openDrawer();
    await flushPromises();

    const labelSelect = wrapper
      .findAllComponents(NSelect)
      .find(
        (select) => select.attributes('data-testid') === 'creation-param-label',
      );
    expect(labelSelect).toBeDefined();
    expect(labelSelect!.props('value')).toBe(0);
    expect(labelSelect!.props('options')).toEqual([
      { label: '__null__', value: 0 },
      { label: 'other', value: 1 },
      { label: 'Null', value: 2 },
    ]);

    (
      document.querySelector('[data-testid="creation-submit"]') as HTMLElement
    ).click();
    await flushPromises();
    expect(
      vi.mocked(submitBacktestRun).mock.calls[0][0].strategy.parameters.label,
    ).toBe('__null__');

    labelSelect!.vm.$emit('update:value', 2);
    await flushPromises();
    (
      document.querySelector('[data-testid="creation-submit"]') as HTMLElement
    ).click();
    await flushPromises();
    expect(
      vi.mocked(submitBacktestRun).mock.calls[1][0].strategy.parameters.label,
    ).toBeNull();
    wrapper.unmount();
  });

  it('shows a required parameter error without submitting an incomplete draft', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([
      {
        ...catalog[0],
        parameters: [
          { name: 'threshold', type: 'int', required: true, nullable: false },
        ],
      },
    ]);
    const wrapper = openDrawer();
    await flushPromises();

    (
      document.querySelector('[data-testid="creation-submit"]') as HTMLElement
    ).click();
    await flushPromises();

    expect(document.body.textContent).toContain('This parameter is required.');
    expect(submitBacktestRun).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
