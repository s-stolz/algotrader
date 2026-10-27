import { flushPromises, mount } from '@vue/test-utils';
import { NInput } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchSweepCapabilities,
  previewParameterSweep,
  submitBacktestBatch,
} from '@/api/backtesterClient';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
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

describe('batch submission', () => {
  sweepSetup();

  it('accepts named and unnamed sweeps without passing names to stateless preview', async () => {
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({
      max_sweep_candidate_count: 1000,
      batch_acceptance_enabled: true,
    });
    vi.mocked(previewParameterSweep).mockImplementation(async (request) =>
      previewFor(request, 2),
    );
    vi.mocked(submitBacktestBatch).mockResolvedValue('named-batch');
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
        (component) => component.attributes('data-testid') === 'creation-name',
      )!;
    for (const [name, expected] of [
      ['  Sweep baseline  ', 'Sweep baseline'],
      ['  ', null],
    ] as const) {
      input.vm.$emit('update:value', name);
      await advancePreview();
      expect(
        vi.mocked(previewParameterSweep).mock.calls.at(-1)?.[0],
      ).not.toHaveProperty('name');
      (
        document.querySelector('[data-testid="sweep-submit"]') as HTMLElement
      ).click();
      await flushPromises();
      expect(submitBacktestBatch).toHaveBeenLastCalledWith(
        expect.not.objectContaining({ name: expect.anything() }),
        expect.any(String),
        expected,
      );
    }
    input.vm.$emit('update:value', 'a'.repeat(121));
    await advancePreview();
    (
      document.querySelector('[data-testid="sweep-submit"]') as HTMLElement
    ).click();
    await flushPromises();
    expect(submitBacktestBatch).toHaveBeenCalledTimes(2);
    expect(document.body.textContent).toContain(
      'Experiment name must have at most 120 characters',
    );
    wrapper.unmount();
  });

  it('uses one submission identity for a reviewed batch retry', async () => {
    vi.mocked(fetchSweepCapabilities).mockResolvedValue({
      max_sweep_candidate_count: 1000,
      batch_acceptance_enabled: true,
    });
    vi.mocked(previewParameterSweep).mockImplementation(async (request) =>
      previewFor(request, 2),
    );
    vi.mocked(submitBacktestBatch)
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValueOnce('batch-1');
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    await advancePreview();
    const submit = document.querySelector(
      '[data-testid="sweep-submit"]',
    ) as HTMLElement;
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
      vi.mocked(submitBacktestBatch).mock.calls[1][1],
    );
    expect(wrapper.emitted('submitted-batch')?.[0]).toEqual(['batch-1']);
    wrapper.unmount();
  });
});
