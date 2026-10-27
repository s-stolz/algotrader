import { flushPromises, mount } from '@vue/test-utils';
import { NDataTable, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  previewParameterSweep,
  submitBacktestRun,
} from '@/api/backtesterClient';
import type {
  SweepPreview,
  SweepPreviewCandidate,
} from '@/types/backtesterContracts';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
  sweepCatalog,
  pinia,
  previewFor,
  deferred,
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

describe('preview lifecycle', () => {
  sweepSetup();

  it('ignores an old preview after a newer draft revision succeeds', async () => {
    const first = deferred<SweepPreview>();
    const second = deferred<SweepPreview>();
    vi.mocked(previewParameterSweep)
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    await flushPromises();
    await advancePreview();
    expect(previewParameterSweep).toHaveBeenCalledTimes(1);
    const capital = wrapper
      .findAllComponents(NInputNumber)
      .find((input) => input.attributes('data-testid') === 'creation-capital');
    capital!.vm.$emit('update:value', 20_000);
    await advancePreview();
    expect(previewParameterSweep).toHaveBeenCalledTimes(2);
    const newRequest = vi.mocked(previewParameterSweep).mock.calls[1][0];
    second.resolve(previewFor(newRequest, 2));
    await flushPromises();
    first.resolve(
      previewFor(vi.mocked(previewParameterSweep).mock.calls[0][0], 1),
    );
    await flushPromises();
    expect(document.querySelector('.preview-counts dd')?.textContent).toBe('2');
    wrapper.unmount();
  });

  it('reviews all candidates with local paging, filtering, and ordinal sort ties', async () => {
    vi.mocked(previewParameterSweep).mockImplementation(async (request) => {
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
      delete result.candidates[1].member_ordinal;
      for (let index = 2; index < result.candidates.length; index += 1) {
        result.candidates[index].member_ordinal = index - 1;
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
    const rows = table.props('data') as SweepPreviewCandidate[];
    expect(rows).toHaveLength(22);
    expect(table.props('pagination')).toMatchObject({ pageSize: 20 });
    const columns = table.props('columns') as Array<{
      title: string;
      sorter?: (a: unknown, b: unknown) => number;
    }>;
    expect(columns.map((column) => column.title)).toEqual([
      'Candidate #',
      'Market',
      'Timeframe',
      'fast_window',
      'Allowed Directions',
      'State',
    ]);
    expect(columns[3]!.sorter!(rows[0]!, rows[2]!)).toBeLessThan(0);
    const filter = wrapper
      .findAllComponents(NSelect)
      .find((select) => select.attributes('data-testid') === 'sweep-filter');
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

  it(
    'refreshes changed catalog metadata without submitting or ' +
      'accepting stale preview',
    async () => {
      vi.mocked(fetchStrategyCatalog)
        .mockResolvedValueOnce(sweepCatalog)
        .mockResolvedValueOnce([
          {
            ...sweepCatalog[0],
            strategy_version: 2,
          },
        ]);
      vi.mocked(previewParameterSweep)
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
        document.body.querySelector('[data-testid="sweep-review"]'),
      ).toBeNull();
      expect(previewParameterSweep).toHaveBeenCalledTimes(1);
      const button = [...document.body.querySelectorAll('button')].find(
        (item) => item.textContent?.includes('Use current version'),
      );
      button!.click();
      await advancePreview();
      expect(previewParameterSweep).toHaveBeenCalledTimes(2);
      expect(
        document.body.querySelector('[data-testid="sweep-review"]'),
      ).not.toBeNull();
      expect(submitBacktestRun).not.toHaveBeenCalled();
      wrapper.unmount();
    },
  );
});
