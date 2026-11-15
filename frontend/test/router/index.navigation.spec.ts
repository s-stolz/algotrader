import { DOMWrapper, flushPromises, mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { describe, expect, it, vi } from 'vitest';
import App from '@/App.vue';
import router from '@/router';

const loading = vi.hoisted(() => {
  let finish!: () => void;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  return { finish, pending, started: vi.fn(), mounted: vi.fn() };
});
vi.mock('@/utils/websocketService', () => ({ wsService: { close: vi.fn() } }));
vi.mock('@/views/ChartView.vue', () => ({
  default: { template: '<input aria-label="Chart selection" />' },
}));
vi.mock('@/views/BacktestWorkspaceView.vue', async () => {
  loading.started();
  await loading.pending;
  return {
    default: {
      mounted: loading.mounted,
      template: '<input aria-label="Backtest draft" />',
    },
  };
});

describe('lazy workspace navigation', () => {
  it('switches immediately, loads on demand, and retains both pages', async () => {
    await router.push('/');
    const wrapper = mount(App, {
      attachTo: document.body,
      global: {
        plugins: [createPinia(), router],
        stubs: { BacktestActivity: true },
      },
    });
    const body = new DOMWrapper(document.body);
    try {
      await vi.dynamicImportSettled();
      await flushPromises();
      const chart = wrapper.get('[aria-label="Chart selection"]');
      await chart.setValue('EURUSD');
      expect(loading.started).not.toHaveBeenCalled();
      await body.get('a[aria-label="Open Backtests"]').trigger('click');
      await flushPromises();
      expect(router.currentRoute.value.path).toBe('/backtests');
      expect(wrapper.get('#workspace-screen').classes()).toContain(
        'workspace-screen--backtests',
      );
      expect(wrapper.find('[aria-label="Loading Backtests"]').exists()).toBe(
        true,
      );
      expect(document.activeElement).toBe(
        wrapper.get('#workspace-screen').element,
      );
      expect(loading.mounted).not.toHaveBeenCalled();
      await body.get('a[aria-label="Return to Chart"]').trigger('click');
      await flushPromises();
      expect(wrapper.get('[aria-label="Chart selection"]').element).toBe(
        chart.element,
      );
      loading.finish();
      await vi.dynamicImportSettled();
      await flushPromises();
      expect(loading.mounted).not.toHaveBeenCalled();
      await router.push('/backtests/saved');
      await flushPromises();
      const draft = wrapper.get('[aria-label="Backtest draft"]');
      await draft.setValue('My draft');
      expect(loading.mounted).toHaveBeenCalledOnce();
      await router.push('/');
      await router.push('/backtests');
      await flushPromises();
      expect(wrapper.get('[aria-label="Backtest draft"]').element).toBe(
        draft.element,
      );
      expect((draft.element as HTMLInputElement).value).toBe('My draft');
      expect(loading.started).toHaveBeenCalledOnce();
      expect(loading.mounted).toHaveBeenCalledOnce();
      expect(wrapper.find('[aria-label="Loading Backtests"]').exists()).toBe(
        false,
      );
    } finally {
      loading.finish();
      await vi.dynamicImportSettled();
      wrapper.unmount();
      router.options.history.destroy();
    }
  });
});
