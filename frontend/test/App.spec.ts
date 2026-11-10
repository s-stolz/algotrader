import { mount, flushPromises } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { defineComponent, h, onMounted } from 'vue';
import { createMemoryHistory, createRouter } from 'vue-router';
import { describe, expect, it, vi } from 'vitest';
import { NAlert, NSplit } from 'naive-ui';
import App from '@/App.vue';
import { designTokens } from '@/design/tokens';
import { wsService } from '@/utils/websocketService';
import { useExecutionLogStore } from '@/stores/executionLogStore';
import { backtestRun } from './api/backtesterClient.fixtures';
import { logPage } from './executionLogFixtures';
vi.mock('@/utils/websocketService', () => ({ wsService: { close: vi.fn() } }));
vi.mock('@/api/executionLogClient', () => ({
  fetchExecutionLog: vi.fn(async () => logPage()),
}));

describe('docked execution workspace', () => {
  it(
    'preserves mounted pages and panel owner through ' +
      'toggles, resize and route changes',
    async () => {
      const mounted = vi.fn();
      const workspaceMounted = vi.fn();
      vi.mocked(wsService.close).mockClear();
      const chart = defineComponent({
        setup() {
          onMounted(mounted);
          return () => h(NAlert, { type: 'error' }, () => 'Upload failed');
        },
      });
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          { path: '/', component: chart },
          {
            path: '/backtests',
            component: defineComponent({
              setup() {
                onMounted(workspaceMounted);
              },
              template: '<div>Backtests</div>',
            }),
          },
        ],
      });
      await router.push('/');
      const pinia = createPinia();
      const wrapper = mount(App, {
        global: { plugins: [pinia, router] },
        attachTo: document.body,
      });
      try {
        const alert = wrapper.get('[role="alert"]').element as HTMLElement;
        expect(alert.style.getPropertyValue('--n-icon-color')).toBe(
          designTokens.color.error,
        );
        expect(wrapper.get('.design-scope').attributes('style')).toContain(
          '--design-font-ui: Tektur, sans-serif',
        );
        const store = useExecutionLogStore(pinia);
        expect(wrapper.find('[role="separator"]').exists()).toBe(false);
        const split = wrapper.getComponent(NSplit);
        expect(split.props('size')).toBe(1);
        store.selectRun(backtestRun());
        await flushPromises();
        const panel = wrapper.get('#execution-log-panel').element;
        expect(split.props('size')).toBe(0.48);
        split.vm.$emit('update:size', 0.65);
        await flushPromises();
        expect(store.splitSize).toBe(0.65);
        await wrapper
          .get('[role="separator"]')
          .trigger('keydown', { key: 'ArrowUp' });
        expect(store.splitSize).toBeCloseTo(0.6);
        store.isOpen = false;
        await flushPromises();
        expect(split.props('size')).toBe(1);
        await router.push('/backtests');
        store.isOpen = true;
        await router.push('/');
        await flushPromises();
        expect(mounted).toHaveBeenCalledTimes(1);
        expect(workspaceMounted).toHaveBeenCalledTimes(1);
        expect(wrapper.get('#execution-log-panel').element).toBe(panel);
        expect(split.props('size')).toBeCloseTo(0.6);
      } finally {
        wrapper.unmount();
        expect(wsService.close).toHaveBeenCalledOnce();
      }
    },
  );
});
