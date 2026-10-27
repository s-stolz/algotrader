import { flushPromises } from '@vue/test-utils';
import { NInputNumber } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import { submitBacktestRun } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { openDrawer, standaloneSetup } from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
  submitBacktestBatch: vi.fn(),
  previewParameterSweep: vi.fn(),
  fetchSweepCapabilities: vi.fn(),
}));

describe('creation design controls', () => {
  standaloneSetup();

  it('retains numeric keyboard editing and requires explicit submission', async () => {
    vi.mocked(submitBacktestRun).mockResolvedValue('keyboard-run');
    const wrapper = openDrawer();
    await flushPromises();
    const capital = wrapper
      .findAllComponents(NInputNumber)
      .find(
        (control) => control.attributes('data-testid') === 'creation-capital',
      )!;
    const input = capital.get('input');
    await input.setValue('12345');
    await input.trigger('keydown', { key: 'Enter' });
    await input.trigger('blur');
    await flushPromises();
    expect(useBacktestWorkspaceStore().creationDraft?.initial_capital).toBe(
      12345,
    );
    expect(submitBacktestRun).not.toHaveBeenCalled();
    document
      .querySelector<HTMLButtonElement>('[data-testid="creation-submit"]')!
      .click();
    await flushPromises();
    expect(submitBacktestRun).toHaveBeenCalledWith(
      expect.objectContaining({ initial_capital: 12345 }),
    );
    wrapper.unmount();
  });
});
