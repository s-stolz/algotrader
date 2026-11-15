import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import BacktestWorkspaceRoute from '@/views/BacktestWorkspaceRoute.vue';

vi.mock('@/views/BacktestWorkspaceView.vue', () => {
  throw new Error('Workspace chunk unavailable');
});

describe('Backtest workspace loading failures', () => {
  it('offers an inline retry and mounts the workspace after recovery', async () => {
    const wrapper = mount(BacktestWorkspaceRoute);
    try {
      expect(wrapper.find('[aria-label="Loading Backtests"]').exists()).toBe(
        true,
      );
      await vi.dynamicImportSettled();
      await flushPromises();
      expect(wrapper.get('[role="alert"]').text()).toContain(
        'Couldn’t load Backtests.',
      );
      vi.doMock('@/views/BacktestWorkspaceView.vue', () => ({
        default: { template: '<main>Backtest workspace loaded</main>' },
      }));
      await wrapper
        .get('[aria-label="Retry: Backtests unavailable"]')
        .trigger('click');
      await vi.dynamicImportSettled();
      await flushPromises();
      expect(wrapper.get('main').text()).toBe('Backtest workspace loaded');
      expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    } finally {
      wrapper.unmount();
    }
  });
});
