import { flushPromises, mount } from '@vue/test-utils';

import { NInput } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchBacktestCapabilities,
  previewBacktest,
  submitBacktest,
} from '@/api/backtesterClient';

import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
  pinia,
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

describe('backtest submission', () => {
  selectionsSetup();

  it(
    'accepts named and unnamed backtests without passing names to ' +
      'stateless preview',
    async () => {
      vi.mocked(fetchBacktestCapabilities).mockResolvedValue({
        max_backtest_candidate_count: 1000,
      });
      vi.mocked(previewBacktest).mockImplementation(async (request) =>
        previewFor(request, 2),
      );
      vi.mocked(submitBacktest).mockResolvedValue('named-backtest');
      const wrapper = mount(BacktestCreationDrawer, {
        props: { show: true },
        global: { plugins: [pinia] },
        attachTo: document.body,
      });
      await flushPromises();
      await advancePreview();
      const input = wrapper
        .findAllComponents(NInput)
        .find(
          (component) =>
            component.attributes('data-testid') === 'creation-name',
        )!;
      for (const [name, expected] of [
        ['  Selections baseline  ', 'Selections baseline'],
        ['  ', null],
      ] as const) {
        input.vm.$emit('update:value', name);
        await advancePreview();
        expect(
          vi.mocked(previewBacktest).mock.calls.at(-1)?.[0],
        ).not.toHaveProperty('name');
        (
          document.querySelector(
            '[data-testid="creation-submit"]',
          ) as HTMLElement
        ).click();
        await flushPromises();
        expect(submitBacktest).toHaveBeenLastCalledWith(
          expect.not.objectContaining({ name: expect.anything() }),
          expect.any(String),
          expected,
        );
      }
      input.vm.$emit('update:value', 'a'.repeat(121));
      await advancePreview();
      (
        document.querySelector('[data-testid="creation-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktest).toHaveBeenCalledTimes(2);
      expect(document.body.textContent).toContain(
        'Experiment name must have at most 120 characters',
      );
      wrapper.unmount();
    },
  );

  it('uses one submission identity for a reviewed backtest retry', async () => {
    vi.mocked(fetchBacktestCapabilities).mockResolvedValue({
      max_backtest_candidate_count: 1000,
    });
    vi.mocked(previewBacktest).mockImplementation(async (request) =>
      previewFor(request, 2),
    );
    vi.mocked(submitBacktest)
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValueOnce('backtest-1');
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    await advancePreview();
    const submit = document.querySelector(
      '[data-testid="creation-submit"]',
    ) as HTMLElement;
    expect(submit).not.toBeNull();
    submit.click();
    await flushPromises();
    expect(submitBacktest).toHaveBeenCalledTimes(1);
    expect(document.body.textContent).toContain('Connection lost');
    await advancePreview();
    submit.click();
    await flushPromises();
    expect(submitBacktest).toHaveBeenCalledTimes(2);
    expect(vi.mocked(submitBacktest).mock.calls[0][1]).toBe(
      vi.mocked(submitBacktest).mock.calls[1][1],
    );
    expect(wrapper.emitted('submitted')?.[0]).toEqual(['backtest-1']);
    wrapper.unmount();
  });
});
