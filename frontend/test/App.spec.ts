import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h, onMounted } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';
import { describe, expect, it, vi } from 'vitest';

import App from '@/App.vue';

const websocketMock = vi.hoisted(() => ({
  close: vi.fn(),
}));

vi.mock('@/utils/websocketService', () => ({
  wsService: {
    close: websocketMock.close,
  },
}));

describe('App', () => {
  it('closes the explicit WebSocket service dependency when unmounted', () => {
    const wrapper = mount(App, {
      global: {
        stubs: {
          'n-config-provider': {
            template: '<div><slot /></div>',
          },
          'router-view': true,
          WorkspaceNavigation: { template: '<div><slot /></div>' },
        },
      },
    });

    wrapper.unmount();

    expect(websocketMock.close).toHaveBeenCalledOnce();
  });

  it('keeps the chart and Workspace mounted across route changes', async () => {
    const chartMounted = vi.fn();
    const workspaceMounted = vi.fn();
    const chart = defineComponent({
      setup() {
        onMounted(chartMounted);
        return () => h('div', { 'data-testid': 'chart-route' }, 'Chart');
      },
    });
    const workspace = defineComponent({
      setup() {
        onMounted(workspaceMounted);
        return () => h('div', { 'data-testid': 'workspace-route' }, 'Workspace');
      },
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: chart },
        { path: '/backtests', component: workspace },
      ],
    });
    await router.push('/');
    await router.isReady();
    const wrapper = mount(App, {
      global: {
        plugins: [router],
        stubs: { 'n-config-provider': { template: '<div><slot /></div>' } },
      },
    });
    await flushPromises();
    expect(wrapper.find('[data-testid="chart-route"]').exists()).toBe(true);

    await wrapper.get('a[aria-label="Open Backtests"]').trigger('click');
    await flushPromises();
    expect(wrapper.find('[data-testid="workspace-route"]').exists()).toBe(true);

    await wrapper.get('a[aria-label="Return to Chart"]').trigger('click');
    await flushPromises();
    expect(wrapper.find('[data-testid="chart-route"]').exists()).toBe(true);
    expect(chartMounted).toHaveBeenCalledOnce();
    expect(workspaceMounted).toHaveBeenCalledOnce();
    wrapper.unmount();
  });
});
