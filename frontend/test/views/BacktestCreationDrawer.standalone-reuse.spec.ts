import { flushPromises } from '@vue/test-utils';
import { NInput, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { reuseStandalone } from '@/views/backtestReuse';
import {
  catalog,
  reuseNames,
  openDrawer,
  standaloneSetup,
} from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
  submitBacktestBatch: vi.fn(),
  previewParameterSweep: vi.fn(),
  fetchSweepCapabilities: vi.fn(),
}));

describe('standalone reuse', () => {
  standaloneSetup();

  it.each(reuseNames)(
    'reviews a copied standalone name %s before creating independent history',
    async (name, proposed, chosen, expected) => {
      const saved = {
        run_id: 'saved-run',
        name,
        request_schema_version: 3,
        status: 'succeeded',
        submitted_at_ms: 1_714_608_000_000,
        request: {
          symbols: ['EURUSD'],
          exchange: 'FX',
          timeframe: 'M15',
          start_ms: 1_714_521_600_000,
          end_ms: 1_714_608_000_000,
          engine: 'vectorized',
          data_granularity: 'bar',
          initial_capital: 20_000,
          strategy: {
            strategy_id: 'sma_crossover',
            strategy_version: 1,
            parameters: {
              enabled: true,
              fast_window: 4,
              label: 'b',
              stop_loss_pct: null,
            },
          },
          execution: {
            signal_timing: 'close',
            fill_timing: 'next_open',
            price_source: 'open',
            allow_partial_fills: false,
            allowed_directions: 'long_and_short',
            trade_accounting_policy: 'average_cost',
            gap_policy: 'skip',
            intrabar_exit_policy: 'conservative',
            commission_bps: 0,
            slippage_bps: 0,
          },
          persist_result: false,
          run_metadata: null,
        },
      } as Parameters<typeof reuseStandalone>[0];
      const original = structuredClone(saved);
      useBacktestWorkspaceStore().createFromSaved(reuseStandalone(saved));
      vi.mocked(fetchStrategyCatalog).mockResolvedValue([
        {
          ...catalog[0],
          strategy_version: 2,
          parameters: catalog[0].parameters.map((parameter) =>
            parameter.name === 'label'
              ? { ...parameter, choices: ['a', 'c'], default: 'c' }
              : parameter,
          ),
        },
      ]);
      vi.mocked(submitBacktestRun).mockResolvedValue('fresh-run');

      let wrapper = openDrawer();
      await flushPromises();
      const nameInput = () =>
        wrapper
          .findAllComponents(NInput)
          .find(
            (input) => input.attributes('data-testid') === 'creation-name',
          )!;
      expect(nameInput().props('value')).toBe(proposed);
      const runType = wrapper
        .findAllComponents(NSelect)
        .find(
          (select) => select.attributes('data-testid') === 'creation-run-type',
        )!;
      runType.vm.$emit('update:value', 'sweep');
      await flushPromises();
      expect(nameInput().props('value')).toBe(proposed);
      runType.vm.$emit('update:value', 'standalone');
      await flushPromises();
      expect(nameInput().props('value')).toBe(proposed);
      expect(document.body.textContent).toContain(
        'Saved sma_crossover version 1',
      );
      expect(document.body.textContent).toContain('current version 2');
      expect(document.body.textContent).toContain(
        'Invalid copied value: label',
      );
      expect(document.body.textContent).toContain(
        'fast_window: saved value 4; current default 5',
      );
      expect(
        (
          document.querySelector(
            '[data-testid="creation-submit"]',
          ) as HTMLButtonElement
        ).disabled,
      ).toBe(true);

      (
        document.querySelector(
          '[data-testid="reuse-use-current"]',
        ) as HTMLElement
      ).click();
      await flushPromises();
      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktestRun).not.toHaveBeenCalled();
      const label = wrapper
        .findAllComponents(NSelect)
        .find(
          (select) =>
            select.attributes('data-testid') === 'creation-param-label',
        );
      label!.vm.$emit('update:value', 1);
      nameInput().vm.$emit('update:value', 'invalid\nname');
      await flushPromises();
      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktestRun).not.toHaveBeenCalled();
      expect(document.body.textContent).toContain(
        'Experiment name must be single-line',
      );
      nameInput().vm.$emit('update:value', chosen);
      await flushPromises();
      wrapper.unmount();
      wrapper = openDrawer();
      await flushPromises();
      expect(nameInput().props('value')).toBe(chosen);
      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktestRun).toHaveBeenCalledWith(
        expect.objectContaining({
          strategy: expect.objectContaining({
            strategy_version: 2,
            parameters: expect.objectContaining({ label: 'c', fast_window: 4 }),
          }),
        }),
      );
      expect(submitBacktestRun).toHaveBeenCalledWith(
        expect.objectContaining({ name: expected }),
      );
      expect(vi.mocked(submitBacktestRun).mock.calls[0][0]).not.toHaveProperty(
        'run_id',
      );
      expect(wrapper.emitted('submitted')?.[0]).toEqual(['fresh-run']);
      expect(saved).toEqual(original);
      wrapper.unmount();
    },
  );

  it('keeps a removed saved strategy inspectable and unavailable for reuse', async () => {
    const saved = {
      run_id: 'removed',
      request_schema_version: 2,
      request: {
        symbols: ['EURUSD'],
        exchange: 'FX',
        timeframe: 'M1',
        start_ms: 1_714_521_600_000,
        end_ms: 1_714_608_000_000,
        engine: 'vectorized',
        data_granularity: 'bar',
        initial_capital: 10_000,
        strategy: { strategy_id: 'retired', parameters: {} },
        execution: {
          signal_timing: 'close',
          fill_timing: 'next_open',
          price_source: 'open',
          allow_partial_fills: false,
          allowed_directions: 'long_and_short',
          trade_accounting_policy: 'average_cost',
          gap_policy: 'skip',
          intrabar_exit_policy: 'conservative',
          commission_bps: 0,
          slippage_bps: 0,
        },
        persist_result: false,
        run_metadata: null,
      },
    } as Parameters<typeof reuseStandalone>[0];
    useBacktestWorkspaceStore().createFromSaved(reuseStandalone(saved));
    const wrapper = openDrawer();
    await flushPromises();
    expect(
      document.querySelector('[data-testid="reuse-removed-strategy"]')
        ?.textContent,
    ).toContain('no longer registered');
    expect(
      (
        document.querySelector(
          '[data-testid="creation-submit"]',
        ) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(submitBacktestRun).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
