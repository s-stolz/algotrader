import {
  mountWorkspace,
  setupWorkspaceTests,
} from './backtestWorkspaceFixtures';
import { flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import {
  fetchStrategyCatalog,
  fetchBacktestCapabilities,
} from '@/api/backtesterClient';
import BacktestCreationDrawer from '@/views/BacktestCreationDrawer.vue';

describe('backtest history loading', () => {
  setupWorkspaceTests();
  it('does not request setup catalogs until creation opens, then retains its session', async () => {
    vi.mocked(fetchStrategyCatalog).mockClear();
    vi.mocked(fetchBacktestCapabilities).mockClear();
    const wrapper = mountWorkspace();
    await flushPromises();
    expect(fetchStrategyCatalog).not.toHaveBeenCalled();
    expect(fetchBacktestCapabilities).not.toHaveBeenCalled();
    expect(wrapper.findComponent(BacktestCreationDrawer).exists()).toBe(false);
    await wrapper.get('[data-testid="workspace-create"]').trigger('click');
    await vi.dynamicImportSettled();
    await flushPromises();
    const drawer = wrapper.getComponent(BacktestCreationDrawer);
    expect(fetchStrategyCatalog).toHaveBeenCalledOnce();
    expect(fetchBacktestCapabilities).toHaveBeenCalledOnce();
    drawer.vm.$emit('update:show', false);
    await flushPromises();
    await wrapper.get('[data-testid="workspace-create"]').trigger('click');
    await flushPromises();
    expect(wrapper.getComponent(BacktestCreationDrawer).props('show')).toBe(
      true,
    );
    expect(fetchStrategyCatalog).toHaveBeenCalledOnce();
    expect(fetchBacktestCapabilities).toHaveBeenCalledOnce();
  });
});
