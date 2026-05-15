import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router';

import ChartView from '@/views/ChartView.vue';

const routes: RouteRecordRaw[] = [
  { path: '/', component: ChartView },
];

const router = createRouter({
  history: createMemoryHistory(),
  routes,
});

export default router;
