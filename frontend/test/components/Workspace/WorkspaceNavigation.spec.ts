import { flushPromises, mount } from '@vue/test-utils';
import { createMemoryHistory, createRouter } from 'vue-router';
import { describe, expect, it } from 'vitest';

import WorkspaceNavigation from '@/components/Workspace/WorkspaceNavigation.vue';

async function mountNavigation(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/backtests', component: { template: '<div />' } },
      { path: '/backtests/:kind/:id', component: { template: '<div />' } },
    ],
  });
  await router.push(path);
  await router.isReady();
  const wrapper = mount(WorkspaceNavigation, {
    attachTo: document.body,
    slots: { default: '<p>Current workspace</p>' },
    global: { plugins: [router] },
  });
  return { router, wrapper };
}

describe('WorkspaceNavigation', () => {
  it('opens Backtests and transfers focus into the destination screen', async () => {
    const { router, wrapper } = await mountNavigation('/');
    try {
      const link = wrapper.get('a[aria-label="Open Backtests"]');
      expect(link.attributes('href')).toBe('/backtests');
      expect(link.attributes('aria-controls')).toBe('workspace-screen');
      await link.trigger('click');
      await flushPromises();

      expect(router.currentRoute.value.path).toBe('/backtests');
      expect(wrapper.get('a').attributes('aria-label')).toBe('Return to Chart');
      const screen = wrapper.get('[aria-label="Backtest workspace"]');
      expect(document.activeElement).toBe(screen.element);
      expect(screen.text()).toBe('Current workspace');
    } finally {
      wrapper.unmount();
    }
  });

  it.each(['/backtests', '/backtests/run/saved', '/backtests/batch/sweep'])(
    'returns to Chart from %s without carrying route parameters', async (path) => {
      const { router, wrapper } = await mountNavigation(path);
      try {
        await wrapper.get('a[aria-label="Return to Chart"]').trigger('click');
        await flushPromises();

        expect(router.currentRoute.value.fullPath).toBe('/');
        expect(wrapper.get('a').attributes('aria-label')).toBe('Open Backtests');
        expect(document.activeElement).toBe(wrapper.get('[aria-label="Chart workspace"]').element);
      } finally {
        wrapper.unmount();
      }
    },
  );
});
