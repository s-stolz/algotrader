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

export default router;
