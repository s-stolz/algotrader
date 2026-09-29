import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router';

import ChartView from '@/views/ChartView.vue';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';

const routes: RouteRecordRaw[] = [
  { path: '/', component: ChartView },
  { path: '/backtests', component: BacktestWorkspaceView },
  { path: '/backtests/:kind(run|batch)/:id', component: BacktestWorkspaceView },
];

const router = createRouter({
  history: createMemoryHistory(),
  routes,
});

// Throwaway navigation prototype: bridge shareable URLs into the memory router.
if (import.meta.env.DEV && new URLSearchParams(window.location.search).has('variant')) {
  const initialVariant = new URLSearchParams(window.location.search).get('variant') || 'A';
  const initialPath = window.location.pathname + window.location.search;
  router.beforeEach((to, from) => {
    if (!to.query.variant) return { path: to.path, query: { ...to.query, variant: from.query.variant || initialVariant } };
  });
  router.afterEach((to) => window.history.replaceState(null, '', to.fullPath));
  void router.isReady().then(() => router.replace(initialPath));
}

export default router;
