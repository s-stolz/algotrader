import {
  createWebHistory,
  createRouter,
  type RouteRecordRaw,
} from 'vue-router';

import ChartWorkspaceRoute from '@/views/ChartWorkspaceRoute.vue';
import BacktestWorkspaceRoute from '@/views/BacktestWorkspaceRoute.vue';

const routes: RouteRecordRaw[] = [
  { path: '/', component: ChartWorkspaceRoute },
  { path: '/backtests', component: BacktestWorkspaceRoute },
  { path: '/backtests/:id', component: BacktestWorkspaceRoute },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
