import { DOMWrapper, flushPromises, mount } from '@vue/test-utils';
import { createMemoryHistory, createRouter } from 'vue-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createPinia, setActivePinia, type Pinia } from 'pinia';
import { useExecutionLogStore } from '@/stores/executionLogStore';
import ExecutionLogPanel from '@/components/Backtest/execution-log/ExecutionLogPanel.vue';
import { backtestRun } from '../../api/backtesterClient.fixtures';
import { logPage } from '../../executionLogFixtures';
vi.mock('@/api/executionLogClient', () => ({
  fetchExecutionLog: vi.fn(async () => logPage()),
}));
let pinia: Pinia;
beforeEach(() => {
  pinia = createPinia();
  setActivePinia(pinia);
});
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
    global: { plugins: [router, pinia] },
  });
  return { router, wrapper };
}

describe('WorkspaceNavigation', () => {
  it(
    'keeps the trade toggle absent until selection, then ' +
      'toggles the dock without a separate hide button',
    async () => {
      const { router, wrapper } = await mountNavigation('/');
      const panel = mount(ExecutionLogPanel, {
        global: { plugins: [router, pinia] },
      });
      try {
        expect(document.body.querySelector('.edge-trades-action')).toBeNull();
        const store = useExecutionLogStore();
        store.selectRun(backtestRun());
        await flushPromises();
        const toggle = new DOMWrapper(document.body).get('.edge-trades-action');
        expect(toggle.attributes('aria-expanded')).toBe('true');
        await toggle.trigger('mousedown');
        await toggle.trigger('mouseup');
        await toggle.trigger('click');
        await flushPromises();
        expect(store.isOpen).toBe(false);
        expect(toggle.attributes('aria-expanded')).toBe('false');
        await toggle.trigger('click');
        await flushPromises();
        expect(store.isOpen).toBe(true);
        await panel.trigger('keydown', { key: 'Escape' });
        expect(store.isOpen).toBe(false);
      } finally {
        panel.unmount();
        wrapper.unmount();
      }
    },
  );
  it('mounts edge controls outside the fixed workspace stacking context', async () => {
    const { wrapper } = await mountNavigation('/');
    try {
      const link = document.querySelector('a[aria-label="Open Backtests"]')!;
      expect(link.closest('.workspace-navigation')).toBeNull();
      expect(link.closest('.edge-right')?.parentElement).toBe(document.body);
      expect(wrapper.get('#workspace-screen').text()).toBe('Current workspace');
    } finally {
      wrapper.unmount();
    }
  });
  it('opens Backtests and transfers focus into the destination screen', async () => {
    const { router, wrapper } = await mountNavigation('/');
    try {
      const link = new DOMWrapper(document.body).get(
        'a[aria-label="Open Backtests"]',
      );
      expect(link.attributes('href')).toBe('/backtests');
      expect(link.attributes('aria-controls')).toBe('workspace-screen');
      await link.trigger('click');
      await flushPromises();

      expect(router.currentRoute.value.path).toBe('/backtests');
      expect(
        new DOMWrapper(document.body).get('a').attributes('aria-label'),
      ).toBe('Return to Chart');
      const screen = wrapper.get('[aria-label="Backtest workspace"]');
      expect(document.activeElement).toBe(screen.element);
      expect(screen.text()).toBe('Current workspace');
    } finally {
      wrapper.unmount();
    }
  });

  it.each([
    '/backtests',
    '/backtests/run/saved',
    '/backtests/backtest/selections',
  ])(
    'returns to Chart from %s without carrying route parameters',
    async (path) => {
      const { router, wrapper } = await mountNavigation(path);
      try {
        await new DOMWrapper(document.body)
          .get('a[aria-label="Return to Chart"]')
          .trigger('click');
        await flushPromises();

        expect(router.currentRoute.value.fullPath).toBe('/');
        expect(
          new DOMWrapper(document.body).get('a').attributes('aria-label'),
        ).toBe('Open Backtests');
        expect(document.activeElement).toBe(
          wrapper.get('[aria-label="Chart workspace"]').element,
        );
      } finally {
        wrapper.unmount();
      }
    },
  );
});
