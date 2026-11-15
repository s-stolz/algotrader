import { createApp, h, type App } from 'vue';
import { RouterView, type Router } from 'vue-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/views/ChartView.vue', () => ({
  default: { template: '<main>Charts</main>' },
}));
vi.mock('@/views/BacktestWorkspaceView.vue', () => ({
  default: { template: '<main>Backtests</main>' },
}));

describe('browser routes', () => {
  let app: App;
  let router: Router;

  async function startAt(path: string) {
    window.history.replaceState(null, '', path);
    vi.resetModules();
    router = (await import('@/router')).default;
    app = createApp({ render: () => h(RouterView) });
    app.use(router);
    await router.isReady();
    app.mount(document.createElement('div'));
  }

  afterEach(() => {
    app?.unmount();
    router?.options.history.destroy();
    window.history.replaceState(null, '', '/');
  });

  it.each(['/', '/backtests', '/backtests/saved-backtest'])(
    'loads %s directly from the browser address',
    async (path) => {
      await startAt(path);
      expect(router.currentRoute.value.path).toBe(path);
      expect(window.location.pathname).toBe(path);
      expect(router.currentRoute.value.params).toEqual(
        path === '/backtests/saved-backtest' ? { id: 'saved-backtest' } : {},
      );
    },
  );

  it('updates the address and follows browser Back and Forward', async () => {
    await startAt('/');
    await router.push('/backtests');
    await router.push('/backtests/saved-backtest');
    expect(window.location.pathname).toBe('/backtests/saved-backtest');

    window.history.back();
    await vi.waitFor(() => {
      expect(router.currentRoute.value.path).toBe('/backtests');
    });
    expect(window.location.pathname).toBe('/backtests');

    window.history.forward();
    await vi.waitFor(() => {
      expect(router.currentRoute.value.params.id).toBe('saved-backtest');
    });
    expect(window.location.pathname).toBe('/backtests/saved-backtest');
  });

  it('redirects an unknown address to charts', async () => {
    await startAt('/unknown/page');
    expect(router.currentRoute.value.path).toBe('/');
    expect(window.location.pathname).toBe('/');
  });
});
