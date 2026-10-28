import { flushPromises, mount } from '@vue/test-utils';
import { NInput, NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  previewParameterSweep,
  submitBacktestBatch,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { SweepPreview } from '@/types/backtesterContracts';
import { reuseStandalone } from '@/views/backtestReuse';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
  advancePreview,
  deferred,
  openDrawer,
  pinia,
  previewFor,
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

describe('creation draft and preview lifetimes', () => {
  sweepSetup();

  it('coalesces edits for 150 ms and invalidates a pending preview on mode change', async () => {
    const pending = deferred<SweepPreview>();
    vi.mocked(previewParameterSweep).mockReturnValueOnce(pending.promise);
    const wrapper = openDrawer();
    await flushPromises();
    const capital = wrapper
      .findAllComponents(NInputNumber)
      .find((input) => input.attributes('data-testid') === 'creation-capital')!;
    await vi.advanceTimersByTimeAsync(100);
    capital.vm.$emit('update:value', 20_000);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(149);
    expect(previewParameterSweep).not.toHaveBeenCalled();
    capital.vm.$emit('update:value', 30_000);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(149);
    expect(previewParameterSweep).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(previewParameterSweep).toHaveBeenCalledTimes(1);
    expect(
      vi.mocked(previewParameterSweep).mock.calls[0][0].initial_capital,
    ).toBe(30_000);
    const mode = wrapper
      .findAllComponents(NSelect)
      .find(
        (select) => select.attributes('data-testid') === 'creation-run-type',
      )!;
    mode.vm.$emit('update:value', 'standalone');
    await flushPromises();
    pending.resolve(
      previewFor(vi.mocked(previewParameterSweep).mock.calls[0][0], 3),
    );
    await flushPromises();
    expect(document.querySelector('[data-testid="sweep-review"]')).toBeNull();
    expect(submitBacktestRun).not.toHaveBeenCalled();
    expect(submitBacktestBatch).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('cancels scheduled previews and ignores errors after unmount', async () => {
    let wrapper = openDrawer();
    await flushPromises();
    wrapper.unmount();
    await advancePreview();
    expect(previewParameterSweep).not.toHaveBeenCalled();

    let reject!: (error: Error) => void;
    vi.mocked(previewParameterSweep).mockReturnValueOnce(
      new Promise((_resolve, fail) => {
        reject = fail;
      }),
    );
    wrapper = openDrawer();
    await advancePreview();
    expect(previewParameterSweep).toHaveBeenCalledTimes(1);
    const catalogReads = vi.mocked(fetchStrategyCatalog).mock.calls.length;
    wrapper.unmount();
    reject(
      new BacktestSubmissionError(
        'strategy_version_unavailable',
        [],
        'Old preview version',
      ),
    );
    await flushPromises();
    expect(fetchStrategyCatalog).toHaveBeenCalledTimes(catalogReads);
    expect(submitBacktestBatch).not.toHaveBeenCalled();
  });

  it('replaces a mounted draft on reuse and retains it after closing the drawer', async () => {
    const pending = deferred<SweepPreview>();
    vi.mocked(previewParameterSweep).mockReturnValueOnce(pending.promise);
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    await advancePreview();
    const store = useBacktestWorkspaceStore();
    store.createFromSaved(
      reuseStandalone({
        run_id: 'saved',
        request_schema_version: 3,
        name: 'Saved experiment',
        request: {
          ...JSON.parse(JSON.stringify(store.creationDraft)),
          initial_capital: 42_000,
        },
      } as Parameters<typeof reuseStandalone>[0]),
    );
    await flushPromises();
    pending.resolve(
      previewFor(vi.mocked(previewParameterSweep).mock.calls[0][0], 9),
    );
    await flushPromises();
    expect(document.querySelector('[data-testid="sweep-review"]')).toBeNull();
    const name = () =>
      wrapper
        .findAllComponents(NInput)
        .find((input) => input.attributes('data-testid') === 'creation-name')!;
    expect(name().props('value')).toBe('Saved experiment (copy)');
    expect(store.creationDraft?.initial_capital).toBe(42_000);
    await wrapper.setProps({ show: false });
    await advancePreview();
    await wrapper.setProps({ show: true });
    await advancePreview();
    expect(name().props('value')).toBe('Saved experiment (copy)');
    expect(store.creationDraft?.initial_capital).toBe(42_000);
    expect(submitBacktestRun).not.toHaveBeenCalled();
    expect(submitBacktestBatch).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
