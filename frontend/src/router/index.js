import { createMemoryHistory, createRouter } from 'vue-router'

import ChartView from '../views/ChartView.vue';

const routes = [
    { path: '/', component: ChartView },
];

const router = createRouter({
    history: createMemoryHistory(),
    routes,
});

export default router;