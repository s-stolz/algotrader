import { flushPromises, mount } from '@vue/test-utils';
import { NInput, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  previewParameterSweep,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
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

describe('sweep parameters', () => {
  sweepSetup();

  it('keeps parameter input modes and sends independent range inputs', async () => {
    vi.mocked(previewParameterSweep).mockImplementation(async (request) =>
      previewFor(request, 2),
    );
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    await flushPromises();
    const mode = wrapper
      .findAllComponents(NSelect)
      .find(
        (select) =>
          select.attributes('data-testid') === 'sweep-mode-fast_window',
      );
    mode!.vm.$emit('update:value', 'range');
    await flushPromises();
    const inputs = wrapper.findAllComponents(NInputNumber);
    const range = inputs.filter(
      (input) => input.attributes('data-testid') === undefined,
    );
    range[0].vm.$emit('update:value', 1);
    range[1].vm.$emit('update:value', 3);
    range[2].vm.$emit('update:value', 1);
    await advancePreview();
    expect(document.body.textContent).toContain('Limit: 1000 candidates');
    expect(previewParameterSweep).toHaveBeenCalledWith(
      expect.objectContaining({
        markets: [1],
        timeframes: ['M1'],
        parameter_axes: {
          fast_window: { mode: 'range', start: 1, stop: 3, step: 1 },
        },
      }),
    );
    expect(document.querySelector('.preview-counts dd')?.textContent).toBe('2');
    expect(submitBacktestRun).not.toHaveBeenCalled();
    mode!.vm.$emit('update:value', 'constant');
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="creation-param-fast_window"]'),
    ).not.toBeNull();
    expect(
      useBacktestWorkspaceStore().creationSweepDraft?.parameters.fast_window
        .rangeStop,
    ).toBe(3);
    wrapper.unmount();
  });

  it(
    'previews exact string values including empty, multiline, ' +
      'and whitespace strings',
    async () => {
      vi.mocked(fetchStrategyCatalog).mockResolvedValue([
        {
          ...sweepCatalog[0],
          parameters: [
            {
              name: 'label',
              type: 'str',
              required: false,
              nullable: false,
              default: 'default',
            },
          ],
        },
      ]);
      vi.mocked(previewParameterSweep).mockImplementation(async (request) =>
        previewFor(request, 1),
      );
      const wrapper = mount(BacktestCreationDrawer, {
        props: { show: true },
        global: { plugins: [pinia] },
        attachTo: document.body,
      });
      await flushPromises();
      const mode = wrapper
        .findAllComponents(NSelect)
        .find(
          (select) => select.attributes('data-testid') === 'sweep-mode-label',
        );
      mode!.vm.$emit('update:value', 'values');
      await advancePreview();
      expect(document.body.textContent).toContain(
        'Select at least one value for label.',
      );

      (
        document.querySelector('[data-testid="sweep-add-label"]') as HTMLElement
      ).click();
      await advancePreview();
      expect(
        vi.mocked(previewParameterSweep).mock.lastCall?.[0].parameter_axes
          .label,
      ).toEqual({
        mode: 'values',
        values: [''],
      });

      (
        document.querySelector('[data-testid="sweep-add-label"]') as HTMLElement
      ).click();
      await flushPromises();
      const multiline = wrapper
        .findAllComponents(NInput)
        .find(
          (input) => input.attributes('data-testid') === 'sweep-string-label-1',
        );
      multiline!.vm.$emit('update:value', 'first\nsecond');
      (
        document.querySelector('[data-testid="sweep-add-label"]') as HTMLElement
      ).click();
      await flushPromises();
      const whitespace = wrapper
        .findAllComponents(NInput)
        .find(
          (input) => input.attributes('data-testid') === 'sweep-string-label-2',
        );
      whitespace!.vm.$emit('update:value', ' ');
      await advancePreview();
      expect(
        vi.mocked(previewParameterSweep).mock.lastCall?.[0].parameter_axes
          .label,
      ).toEqual({
        mode: 'values',
        values: ['', 'first\nsecond', ' '],
      });
      expect(
        useBacktestWorkspaceStore().creationSweepDraft?.parameters.label
          .stringValues,
      ).toEqual(['', 'first\nsecond', ' ']);

      (
        document.querySelector(
          '[data-testid="sweep-remove-label-0"]',
        ) as HTMLElement
      ).click();
      await advancePreview();
      expect(
        vi.mocked(previewParameterSweep).mock.lastCall?.[0].parameter_axes
          .label,
      ).toEqual({
        mode: 'values',
        values: ['first\nsecond', ' '],
      });
      wrapper.unmount();
    },
  );
});
