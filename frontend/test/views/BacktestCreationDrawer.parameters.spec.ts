import { flushPromises, mount } from '@vue/test-utils';

import { NInput, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  previewBacktest,
  submitBacktest,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';

import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
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

describe('selections parameters', () => {
  selectionsSetup();

  it('keeps parameter input modes and sends independent range inputs', async () => {
    vi.mocked(previewBacktest).mockImplementation(async (request) =>
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
          select.attributes('data-testid') === 'selections-mode-fast_window',
      );
    mode!.vm.$emit('update:value', 'range');
    await flushPromises();
    const inputs = wrapper.findAllComponents(NInputNumber);
    const range = inputs.filter((input) =>
      input.attributes('data-testid')?.startsWith('selections-'),
    );
    range[0].vm.$emit('update:value', 1);
    range[1].vm.$emit('update:value', 3);
    range[2].vm.$emit('update:value', 1);
    await advancePreview();
    expect(document.body.textContent).toContain('Limit: 1000 candidates');
    expect(previewBacktest).toHaveBeenCalledWith(
      expect.objectContaining({
        markets: [1],
        timeframes: ['M1'],
        parameter_axes: {
          fast_window: { mode: 'range', start: 1, stop: 3, step: 1 },
        },
      }),
    );
    expect(document.querySelector('.preview-counts dd')?.textContent).toBe('2');
    expect(submitBacktest).not.toHaveBeenCalled();
    mode!.vm.$emit('update:value', 'constant');
    await flushPromises();
    expect(
      document.body.querySelector('[data-testid="creation-param-fast_window"]'),
    ).not.toBeNull();
    expect(
      useBacktestWorkspaceStore().creationSelections?.parameters.fast_window
        .rangeStop,
    ).toBe(3);
    wrapper.unmount();
  });

  it(
    'previews exact string values including empty, multiline, and ' +
      'whitespace strings',
    async () => {
      vi.mocked(fetchStrategyCatalog).mockResolvedValue([
        {
          ...selectionsCatalog[0],
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
      vi.mocked(previewBacktest).mockImplementation(async (request) =>
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
          (select) =>
            select.attributes('data-testid') === 'selections-mode-label',
        );
      mode!.vm.$emit('update:value', 'values');
      await advancePreview();
      expect(document.body.textContent).toContain(
        'Select at least one value for label.',
      );

      (
        document.querySelector(
          '[data-testid="selections-add-label"]',
        ) as HTMLElement
      ).click();
      await advancePreview();
      expect(
        vi.mocked(previewBacktest).mock.lastCall?.[0].parameter_axes.label,
      ).toEqual({
        mode: 'values',
        values: [''],
      });

      (
        document.querySelector(
          '[data-testid="selections-add-label"]',
        ) as HTMLElement
      ).click();
      await flushPromises();
      const multiline = wrapper
        .findAllComponents(NInput)
        .find(
          (input) =>
            input.attributes('data-testid') === 'selections-string-label-1',
        );
      multiline!.vm.$emit('update:value', 'first\nsecond');
      (
        document.querySelector(
          '[data-testid="selections-add-label"]',
        ) as HTMLElement
      ).click();
      await flushPromises();
      const whitespace = wrapper
        .findAllComponents(NInput)
        .find(
          (input) =>
            input.attributes('data-testid') === 'selections-string-label-2',
        );
      whitespace!.vm.$emit('update:value', ' ');
      await advancePreview();
      expect(
        vi.mocked(previewBacktest).mock.lastCall?.[0].parameter_axes.label,
      ).toEqual({
        mode: 'values',
        values: ['', 'first\nsecond', ' '],
      });
      expect(
        useBacktestWorkspaceStore().creationSelections?.parameters.label
          .stringValues,
      ).toEqual(['', 'first\nsecond', ' ']);

      (
        document.querySelector(
          '[data-testid="selections-remove-label-0"]',
        ) as HTMLElement
      ).click();
      await advancePreview();
      expect(
        vi.mocked(previewBacktest).mock.lastCall?.[0].parameter_axes.label,
      ).toEqual({
        mode: 'values',
        values: ['first\nsecond', ' '],
      });
      wrapper.unmount();
    },
  );
  it('resets parameter values and modes when deliberately switching strategies', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([
      selectionsCatalog[0],
      {
        ...selectionsCatalog[0],
        strategy_id: 'other',
        parameters: [{ ...selectionsCatalog[0].parameters[0], default: 20 }],
      },
    ]);
    vi.mocked(previewBacktest).mockImplementation(async (request) =>
      previewFor(request, 1),
    );
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    try {
      await advancePreview();
      const store = useBacktestWorkspaceStore();
      const select = (id: string) =>
        wrapper
          .findAllComponents(NSelect)
          .find((control) => control.attributes('data-testid') === id)!;
      select('selections-mode-fast_window').vm.$emit('update:value', 'range');
      await flushPromises();
      select('creation-strategy').vm.$emit('update:value', 'other');
      await advancePreview();
      expect(store.creationDraft?.strategy.parameters.fast_window).toBe(20);
      expect(store.creationSelections?.parameters.fast_window.mode).toBe(
        'constant',
      );
      select('creation-strategy').vm.$emit('update:value', 'sma_crossover');
      await advancePreview();
      expect(store.creationDraft?.strategy.parameters.fast_window).toBe(5);
      expect(
        vi.mocked(previewBacktest).mock.lastCall?.[0].parameter_axes,
      ).toEqual({
        fast_window: { mode: 'constant', value: 5 },
      });
    } finally {
      wrapper.unmount();
    }
  });
});
