import { flushPromises, mount } from '@vue/test-utils';

import { NDataTable, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  previewBacktest,
  submitBacktest,
} from '@/api/backtesterClient';

import type {
  BacktestPreview,
  BacktestPreviewCandidate,
} from '@/types/backtesterContracts';

import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
  pinia,
  selectionsCatalog,
  previewFor,
  deferred,
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

describe('preview lifecycle', () => {
  selectionsSetup();

  it('ignores an old preview after a newer draft revision succeeds', async () => {
    const first = deferred<BacktestPreview>();
    const second = deferred<BacktestPreview>();
    vi.mocked(previewBacktest)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    await flushPromises();
    await advancePreview();
    expect(previewBacktest).toHaveBeenCalledTimes(1);
    const capital = wrapper
      .findAllComponents(NInputNumber)
      .find((input) => input.attributes('data-testid') === 'creation-capital');
    capital!.vm.$emit('update:value', 20_000);
    await advancePreview();
    expect(previewBacktest).toHaveBeenCalledTimes(2);
    const newRequest = vi.mocked(previewBacktest).mock.calls[1][0];
    second.resolve(previewFor(newRequest, 2));
    await flushPromises();
    first.resolve(previewFor(vi.mocked(previewBacktest).mock.calls[0][0], 1));
    await flushPromises();
    expect(document.querySelector('.preview-counts dd')?.textContent).toBe('2');
    wrapper.unmount();
  });

  it(
    'reviews all candidates with local paging, filtering, and ordinal ' +
      'sort ties',
    async () => {
      vi.mocked(previewBacktest).mockImplementation(async (request) => {
        const result = previewFor(request, 22);
        result.candidates[1] = {
          ...result.candidates[1],
          status: 'excluded',
          issues: [
            {
              code: 'invalid_parameter_combination',
              fields: ['fast_window'],
              message: 'Excluded combination',
            },
          ],
        };
        delete result.candidates[1].request;
        delete result.candidates[1].run_ordinal;
        for (let index = 2; index < result.candidates.length; index += 1) {
          result.candidates[index].run_ordinal = index - 1;
        }
        result.ready_count = 21;
        result.excluded_count = 1;
        return result;
      });
      const wrapper = mount(BacktestCreationDrawer, {
        props: { show: true },
        global: { plugins: [pinia] },
        attachTo: document.body,
      });
      await flushPromises();
      await advancePreview();
      const table = wrapper.findComponent(NDataTable);
      const rows = table.props('data') as BacktestPreviewCandidate[];
      expect(rows).toHaveLength(22);
      expect(table.props('pagination')).toMatchObject({ pageSize: 10 });
      const columns = table.props('columns') as Array<{
        title: string;
        sorter?: (a: unknown, b: unknown) => number;
      }>;
      expect(columns.map((column) => column.title)).toEqual([
        '#',
        'Market',
        'Timeframe',
        'fast_window',
        'Allowed Directions',
        'State',
      ]);
      expect(columns[3]!.sorter!(rows[0]!, rows[2]!)).toBeLessThan(0);
      const filter = wrapper
        .findAllComponents(NSelect)
        .find(
          (select) => select.attributes('data-testid') === 'selections-filter',
        );
      filter!.vm.$emit('update:value', 'excluded');
      await flushPromises();
      const excludedRows = table.props('data') as BacktestPreviewCandidate[];
      expect(excludedRows).toHaveLength(1);
      expect(excludedRows[0]!.issues?.[0]?.message).toBe(
        'Excluded combination',
      );
      filter!.vm.$emit('update:value', 'ready');
      await flushPromises();
      expect(table.props('data')).toHaveLength(21);
      wrapper.unmount();
    },
  );

  it(
    'refreshes changed catalog metadata without submitting or ' +
      'accepting stale preview',
    async () => {
      vi.mocked(fetchStrategyCatalog)
        .mockResolvedValueOnce(selectionsCatalog)
        .mockResolvedValueOnce([
          {
            ...selectionsCatalog[0],
            strategy_version: 2,
          },
        ]);
      vi.mocked(previewBacktest)
        .mockRejectedValueOnce(
          new BacktestSubmissionError(
            'strategy_version_unavailable',
            [],
            'Strategy version is unavailable',
          ),
        )
        .mockImplementation(async (request) => previewFor(request, 1));
      const wrapper = mount(BacktestCreationDrawer, {
        props: { show: true },
        global: { plugins: [pinia] },
        attachTo: document.body,
      });
      await flushPromises();
      await advancePreview();
      expect(fetchStrategyCatalog).toHaveBeenCalledTimes(2);
      expect(document.body.textContent).toContain('Strategy version changed');
      expect(
        document.body.querySelector('[data-testid="selections-review"]'),
      ).toBeNull();
      expect(previewBacktest).toHaveBeenCalledTimes(1);
      const button = [...document.body.querySelectorAll('button')].find(
        (item) => item.textContent?.includes('Use current version'),
      );
      button!.click();
      await advancePreview();
      expect(previewBacktest).toHaveBeenCalledTimes(2);
      expect(
        document.body.querySelector('[data-testid="selections-review"]'),
      ).not.toBeNull();
      expect(submitBacktest).not.toHaveBeenCalled();
      wrapper.unmount();
    },
  );
});
