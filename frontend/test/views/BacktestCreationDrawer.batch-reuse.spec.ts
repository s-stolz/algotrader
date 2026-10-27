import { flushPromises, mount } from '@vue/test-utils';
import { NInput, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  fetchSweepCapabilities,
  previewParameterSweep,
  submitBacktestBatch,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { BacktestBatch } from '@/types/backtesterContracts';
import { reuseBatch } from '@/views/backtestReuse';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
  reuseNames,
  sweepCatalog,
  pinia,
  previewFor,
  advancePreview,
  sweepSetup,
} from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
  submitBacktestBatch: vi.fn(),
  previewParameterSweep: vi.fn(),
  fetchSweepCapabilities: vi.fn(),
}));

describe('batch reuse', () => {
  sweepSetup();

  it.each(reuseNames)(
    'revalidates a copied batch name %s with a fresh identity',
    async (name, proposed, chosen, expected) => {
      const batch = {
        batch_id: 'saved-batch',
        name,
        submission_id: 'old-submission',
        strategy_id: 'sma_crossover',
        strategy_version: 1,
        accepted_definition: {
          shared_request: {
            symbols: [],
            exchange: null,
            timeframe: 'M1',
            start_ms: 1_714_521_600_000,
            end_ms: 1_714_608_000_000,
            engine: 'vectorized',
            data_granularity: 'bar',
            initial_capital: 10_000,
            strategy: {
              strategy_id: 'sma_crossover',
              strategy_version: 1,
              parameters: {},
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
          normalized_selections: {
            markets: [
              { symbol_id: 9, symbol: 'GONE', exchange: 'FX' },
              { symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' },
            ],
            timeframes: ['H1', 'M1'],
            allowed_directions: ['short_only', 'long_and_short'],
            parameters: {
              fast_window: {
                mode: 'range',
                values: [3, 5],
                range: { start: 3, stop: 5, step: 2 },
              },
              slow_window: { mode: 'default', values: [20] },
            },
          },
        },
        strategy_metadata: {
          strategy_id: 'sma_crossover',
          strategy_version: 1,
          display_name: 'SMA',
          parameters: [
            {
              name: 'fast_window',
              type: 'int',
              required: false,
              nullable: false,
              default: 3,
            },
            {
              name: 'slow_window',
              type: 'int',
              required: false,
              nullable: false,
              default: 20,
            },
          ],
        },
      } as unknown as BacktestBatch;
      const original = structuredClone(batch);
      useBacktestWorkspaceStore().createFromSaved(reuseBatch(batch));
      vi.mocked(fetchStrategyCatalog).mockResolvedValue([
        {
          ...sweepCatalog[0],
          strategy_version: 2,
          parameters: [
            ...sweepCatalog[0].parameters,
            {
              name: 'slow_window',
              type: 'int',
              required: false,
              nullable: false,
              default: 30,
            },
          ],
        },
      ]);
      vi.mocked(fetchSweepCapabilities).mockResolvedValue({
        max_sweep_candidate_count: 1000,
        batch_acceptance_enabled: true,
      });
      vi.mocked(previewParameterSweep)
        .mockRejectedValueOnce(
          new Error('Raw candidate count exceeds current limit'),
        )
        .mockImplementation(async (request) => {
          const result = previewFor(request, 2);
          result.candidates[1] = {
            ...result.candidates[1],
            status: 'excluded',
            issues: [
              {
                code: 'invalid_parameter_combination',
                fields: ['fast_window'],
                message: 'Current validator excludes this combination',
              },
            ],
          };
          delete result.candidates[1].request;
          delete result.candidates[1].member_ordinal;
          result.ready_count = 1;
          result.excluded_count = 1;
          return result;
        });
      vi.mocked(submitBacktestBatch).mockResolvedValue('fresh-batch');
      let wrapper = mount(BacktestCreationDrawer, {
        props: { show: true },
        global: { plugins: [pinia] },
        attachTo: document.body,
      });
      await advancePreview();
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
      runType.vm.$emit('update:value', 'standalone');
      await flushPromises();
      expect(nameInput().props('value')).toBe(proposed);
      runType.vm.$emit('update:value', 'sweep');
      await advancePreview();
      expect(nameInput().props('value')).toBe(proposed);
      nameInput().vm.$emit('update:value', chosen);
      await flushPromises();
      wrapper.unmount();
      wrapper = mount(BacktestCreationDrawer, {
        props: { show: true },
        global: { plugins: [pinia] },
        attachTo: document.body,
      });
      await advancePreview();
      expect(nameInput().props('value')).toBe(chosen);
      expect(document.body.textContent).toContain(
        'Saved sma_crossover version 1',
      );
      expect(document.body.textContent).toContain(
        'slow_window default changed: 20 → 30',
      );
      expect(document.body.textContent).toContain(
        'Saved Market ID 9 unavailable',
      );
      expect(previewParameterSweep).not.toHaveBeenCalled();

      (
        document.querySelector(
          '[data-testid="reuse-use-current"]',
        ) as HTMLElement
      ).click();
      await flushPromises();
      const market = wrapper
        .findAllComponents(NSelect)
        .find((select) => select.attributes('data-testid') === 'sweep-markets');
      market!.vm.$emit('update:value', [1]);
      await advancePreview();
      expect(document.body.textContent).toContain(
        'Raw candidate count exceeds current limit',
      );
      expect(submitBacktestBatch).not.toHaveBeenCalled();
      const capital = wrapper
        .findAllComponents(NInputNumber)
        .find(
          (input) => input.attributes('data-testid') === 'creation-capital',
        );
      capital!.vm.$emit('update:value', 12_000);
      await advancePreview();
      expect(previewParameterSweep).toHaveBeenCalledWith(
        expect.objectContaining({
          markets: [1],
          timeframes: ['H1', 'M1'],
          allowed_directions: ['short_only', 'long_and_short'],
          strategy: { strategy_id: 'sma_crossover', strategy_version: 2 },
          parameter_axes: {
            fast_window: { mode: 'range', start: 3, stop: 5, step: 2 },
            slow_window: { mode: 'constant', value: 30 },
          },
        }),
      );
      expect(
        document.querySelectorAll('.preview-counts dd')[2]?.textContent,
      ).toBe('1');
      (
        document.querySelector('[data-testid="sweep-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktestBatch).toHaveBeenCalledWith(
        expect.anything(),
        expect.not.stringContaining('old-submission'),
        expected,
      );
      expect(
        vi.mocked(submitBacktestBatch).mock.calls[0][0],
      ).not.toHaveProperty('name');
      expect(
        vi.mocked(submitBacktestBatch).mock.calls[0][0],
      ).not.toHaveProperty('batch_id');
      expect(
        vi.mocked(previewParameterSweep).mock.calls.at(-1)?.[0],
      ).not.toHaveProperty('name');
      expect(wrapper.emitted('submitted-batch')?.[0]).toEqual(['fresh-batch']);
      expect(batch).toEqual(original);
      wrapper.unmount();
    },
  );
});
