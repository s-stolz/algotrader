import { mount, flushPromises } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';
import { describe, it, expect, vi } from 'vitest';
import App from '@/App.vue';
import BacktestActivity from '@/components/Backtest/activity/BacktestActivity.vue';
import { fetchBacktestQueue } from '@/api/backtesterClient';
import { installBacktestSocket } from './backtestEventSocket';
import {
  healthySnapshot,
  backtest,
} from './components/Backtest/activity/backtestActivityFixtures';

vi.mock('@/api/backtesterClient', () => ({
  fetchBacktestQueue: vi.fn(),
  getBacktest: vi.fn(async () => backtest),
}));

describe('application activity', () => {
  it('shows activity only in the upper backtest pane and opens selected work', async () => {
    installBacktestSocket();
    vi.mocked(fetchBacktestQueue).mockResolvedValue({
      ...healthySnapshot,
      snapshot_at_ms: Date.now(),
      last_heartbeat_ms: Date.now(),
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Chart</div>' } },
        {
          path: '/backtests/:id?',
          component: { template: '<div>Backtests</div>' },
        },
      ],
    });
    await router.push('/');
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          WorkspaceNavigation: { template: '<div><slot /></div>' },
          ExecutionLogPanel: true,
        },
      },
    });
    try {
      await flushPromises();
      expect(wrapper.findComponent(BacktestActivity).exists()).toBe(false);
      expect(fetchBacktestQueue).not.toHaveBeenCalled();
      await router.push('/backtests');
      await flushPromises();
      const activity = wrapper.getComponent(BacktestActivity);
      expect(
        wrapper.get('.primary-workspace').element.contains(activity.element),
      ).toBe(true);
      expect(activity.get('[data-testid="activity-toggle"]').text()).toBe(
        '1 running · 1 queued',
      );
      activity.vm.$emit('inspect', 'backtest-1');
      await flushPromises();
      expect(router.currentRoute.value.path).toBe('/backtests/backtest-1');
      expect(wrapper.getComponent(BacktestActivity).element).toBe(
        activity.element,
      );
      await router.push('/');
      await flushPromises();
      expect(wrapper.findComponent(BacktestActivity).exists()).toBe(false);
      expect(fetchBacktestQueue).toHaveBeenCalledOnce();
    } finally {
      wrapper.unmount();
    }
  });
});
