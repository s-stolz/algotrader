import { NSelect } from 'naive-ui';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { fetchStrategyCatalog } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { catalog, openDrawer, creationSetup } from './creationFixtures';
vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));
describe('strategy execution mode', () => {
  creationSetup();
  it('derives execution mode when selecting a strategy', async () => {
    vi.mocked(fetchStrategyCatalog).mockResolvedValue([
      { ...catalog[0], execution_mode: 'orders' },
      {
        ...catalog[0],
        strategy_id: 'target_strategy',
        execution_mode: 'targets',
      },
    ]);
    const wrapper = openDrawer();
    await flushPromises();
    const store = useBacktestWorkspaceStore();
    expect(store.creationDraft?.execution.execution_mode).toBe('orders');
    expect(
      document.body.textContent?.match(/Spread \(price units\)/g),
    ).toHaveLength(1);
    expect(document.querySelector('[aria-label="Execution mode"]')).toBeNull();
    wrapper
      .findAllComponents(NSelect)
      .find((select) => select.props('value') === 'sma_crossover')!
      .vm.$emit('update:value', 'target_strategy');
    await flushPromises();
    expect(store.creationDraft?.execution.execution_mode).toBe('targets');
    expect(document.body.textContent).not.toContain('Spread (price units)');
    wrapper.unmount();
  });
});
