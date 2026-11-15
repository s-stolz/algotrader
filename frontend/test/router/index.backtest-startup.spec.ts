import { DOMWrapper, flushPromises, mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { expect, it, vi } from 'vitest';
import App from '@/App.vue';
import router from '@/router';

const chart = vi.hoisted(() => {
  let finish!: () => void;
  const pending = new Promise<void>((resolve) => {
    finish = resolve;
  });
  return { pending, finish, loaded: vi.fn(), mounted: vi.fn() };
});
vi.mock('@/utils/websocketService', () => ({ wsService: { close: vi.fn() } }));
vi.mock('@/views/BacktestWorkspaceView.vue', () => ({
  default: { template: '<input aria-label="Backtest draft" />' },
}));
vi.mock('@/views/ChartView.vue', async () => {
  chart.loaded();
  await chart.pending;
  return {
    default: { mounted: chart.mounted, template: '<main>Loaded chart</main>' },
  };
});

it('loads Chart on demand after a Backtests reload', async () => {
  await router.push('/backtests/saved');
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
    const draft = wrapper.get('[aria-label="Backtest draft"]');
    await draft.setValue('Retained draft');
    expect(chart.loaded).not.toHaveBeenCalled();
    await body.get('a[aria-label="Return to Chart"]').trigger('click');
    await flushPromises();
    expect(router.currentRoute.value.path).toBe('/');
    expect(wrapper.get('#workspace-screen').classes()).toContain(
      'workspace-screen--chart',
    );
    expect(wrapper.find('[aria-label="Loading Chart"]').exists()).toBe(true);
    expect(chart.mounted).not.toHaveBeenCalled();
    await body.get('a[aria-label="Open Backtests"]').trigger('click');
    await flushPromises();
    chart.finish();
    await vi.dynamicImportSettled();
    await flushPromises();
    expect(chart.mounted).not.toHaveBeenCalled();
    expect(wrapper.get('[aria-label="Backtest draft"]').element).toBe(
      draft.element,
    );
    await router.push('/');
    await flushPromises();
    expect(wrapper.get('main').text()).toBe('Loaded chart');
    expect(chart.loaded).toHaveBeenCalledOnce();
    expect(chart.mounted).toHaveBeenCalledOnce();
  } finally {
    chart.finish();
    await vi.dynamicImportSettled();
    wrapper.unmount();
    router.options.history.destroy();
  }
});
