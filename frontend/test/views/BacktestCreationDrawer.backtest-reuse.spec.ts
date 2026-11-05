import { flushPromises, mount } from '@vue/test-utils';

import { NInput, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  fetchBacktestCapabilities,
  previewBacktest,
  submitBacktest,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import type { Backtest } from '@/types/backtesterContracts';
import { reuseBacktest } from '@/views/backtestReuse';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
  reuseNames,
  pinia,
  selectionsCatalog,
  previewFor,
  advancePreview,
  selectionsSetup,
} from './creationFixtures';
vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));

describe('backtest reuse', () => {
  selectionsSetup();

  it.each(reuseNames)(
    'revalidates a copied backtest name %s with a fresh identity',
    async (name, proposed, chosen, expected) => {
      const batch = {
        backtest_id: 'saved-batch',
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
      } as unknown as Backtest;
      const original = structuredClone(batch);
      useBacktestWorkspaceStore().createFromSaved(reuseBacktest(batch));
      vi.mocked(fetchStrategyCatalog).mockResolvedValue([
        {
          ...selectionsCatalog[0],
          strategy_version: 2,
          parameters: [
            ...selectionsCatalog[0].parameters,
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
      vi.mocked(fetchBacktestCapabilities).mockResolvedValue({
        max_backtest_candidate_count: 1000,
      });
      vi.mocked(previewBacktest)
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
          delete result.candidates[1].run_ordinal;
          result.ready_count = 1;
          result.excluded_count = 1;
          return result;
        });
      vi.mocked(submitBacktest).mockResolvedValue('fresh-batch');
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
      expect(
        document
          .querySelector('[data-testid="reuse-version-review"]')
          ?.getAttribute('aria-label'),
      ).toBe('Copied from v1. Now using v2 because v1 is unavailable.');
      expect(
        document.querySelector('[data-testid="reuse-use-current"]'),
      ).toBeNull();
      expect(
        document
          .querySelector('[aria-label^="slow_window changes"]')
          ?.getAttribute('aria-label'),
      ).toContain('Default: 20 → 30');
      expect(document.body.textContent).toContain(
        'Saved Market ID 9 unavailable',
      );
      expect(previewBacktest).not.toHaveBeenCalled();
      const market = wrapper
        .findAllComponents(NSelect)
        .find(
          (select) => select.attributes('data-testid') === 'selections-markets',
        );
      market!.vm.$emit('update:value', [1]);
      await advancePreview();
      expect(document.body.textContent).toContain(
        'Raw candidate count exceeds current limit',
      );
      expect(submitBacktest).not.toHaveBeenCalled();
      const capital = wrapper
        .findAllComponents(NInputNumber)
        .find(
          (input) => input.attributes('data-testid') === 'creation-capital',
        );
      capital!.vm.$emit('update:value', 12_000);
      await advancePreview();
      expect(previewBacktest).toHaveBeenCalledWith(
        expect.objectContaining({
          markets: [1],
          timeframes: ['H1', 'M1'],
          allowed_directions: ['short_only', 'long_and_short'],
          strategy: { strategy_id: 'sma_crossover', strategy_version: 2 },
          parameter_axes: {
            fast_window: { mode: 'range', start: 3, stop: 5, step: 2 },
            slow_window: { mode: 'constant', value: 20 },
          },
        }),
      );
      expect(
        document.querySelectorAll('.preview-counts dd')[2]?.textContent,
      ).toBe('1');
      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktest).toHaveBeenCalledWith(
        expect.anything(),
        expect.not.stringContaining('old-submission'),
        expected,
      );
      expect(vi.mocked(submitBacktest).mock.calls[0][0]).not.toHaveProperty(
        'name',
      );
      expect(vi.mocked(submitBacktest).mock.calls[0][0]).not.toHaveProperty(
        'backtest_id',
      );
      expect(
        vi.mocked(previewBacktest).mock.calls.at(-1)?.[0],
      ).not.toHaveProperty('name');
      expect(wrapper.emitted('submitted')?.[0]).toEqual(['fresh-batch']);
      expect(batch).toEqual(original);
      wrapper.unmount();
    },
  );
});
