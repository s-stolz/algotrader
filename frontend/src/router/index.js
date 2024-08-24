import { createMemoryHistory, createRouter } from 'vue-router'

import ChartPage from '../components/page/Chart/ChartPage.vue';
import DataPage from '../components/page/Data/DataPage.vue';

const routes = [
    { path: '/', component: ChartPage },
    { path: '/Data', component: DataPage }
];

const router = createRouter({
    history: createMemoryHistory(),
    routes,
});

export default router;