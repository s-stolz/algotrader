import { flushPromises, mount } from '@vue/test-utils';
import { NInput } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  previewBacktest,
  submitBacktest,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import type { BacktestPreview } from '@/types/backtesterContracts';
import { reuseRun } from '@/views/backtestReuse';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';
import {
  advancePreview,
  deferred,
  openDrawer,
  pinia,
  previewFor,
  selectionsSetup,
} from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));

describe('creation draft and preview lifetimes', () => {
  selectionsSetup();

  it('cancels scheduled previews and ignores errors after unmount', async () => {
    let wrapper = openDrawer();
    await flushPromises();
    wrapper.unmount();
    await advancePreview();
    expect(previewBacktest).not.toHaveBeenCalled();

    let reject!: (error: Error) => void;
    vi.mocked(previewBacktest).mockReturnValueOnce(
      new Promise((_resolve, fail) => {
        reject = fail;
      }),
    );
    wrapper = openDrawer();
    await advancePreview();
    expect(previewBacktest).toHaveBeenCalledTimes(1);
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
    expect(submitBacktest).not.toHaveBeenCalled();
  });

  it('replaces a mounted draft on reuse and retains it after closing the drawer', async () => {
    const pending = deferred<BacktestPreview>();
    vi.mocked(previewBacktest).mockReturnValueOnce(pending.promise);
    const wrapper = mount(BacktestCreationDrawer, {
      props: { show: true },
      global: { plugins: [pinia] },
      attachTo: document.body,
    });
    await advancePreview();
    const store = useBacktestWorkspaceStore();
    store.createFromSaved(
      reuseRun(
        {
          run_id: 'saved',
          request_schema_version: 3,
          backtest_id: 'source',
          run_ordinal: 0,
          status: 'succeeded',
          submitted_at_ms: 1,
          request: {
            ...JSON.parse(JSON.stringify(store.creationDraft)),
            initial_capital: 42_000,
          },
        } as Parameters<typeof reuseRun>[0],
        [{ symbol_id: 1, symbol: 'EURUSD', exchange: 'FX' }],
      ),
    );
    await flushPromises();
    pending.resolve(previewFor(vi.mocked(previewBacktest).mock.calls[0][0], 9));
    await flushPromises();
    expect(
      document.querySelector('[data-testid="selections-review"]'),
    ).toBeNull();
    const name = () =>
      wrapper
        .findAllComponents(NInput)
        .find((input) => input.attributes('data-testid') === 'creation-name')!;
    expect(name().props('value')).toBe('');
    expect(store.creationDraft?.initial_capital).toBe(42_000);
    await wrapper.setProps({ show: false });
    await advancePreview();
    await wrapper.setProps({ show: true });
    await advancePreview();
    expect(name().props('value')).toBe('');
    expect(store.creationDraft?.initial_capital).toBe(42_000);
    expect(submitBacktest).not.toHaveBeenCalled();
    expect(submitBacktest).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
