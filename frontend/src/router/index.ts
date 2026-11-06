import {
  createWebHistory,
  createRouter,
  type RouteRecordRaw,
} from 'vue-router';

import ChartView from '@/views/ChartView.vue';
import BacktestWorkspaceView from '@/views/BacktestWorkspaceView.vue';

const routes: RouteRecordRaw[] = [
  { path: '/', component: ChartView },
  { path: '/backtests', component: BacktestWorkspaceView },
  { path: '/backtests/:id', component: BacktestWorkspaceView },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
