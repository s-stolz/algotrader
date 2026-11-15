import { resolveWebsocketUrl } from './utils/websocketUrl';
import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { installDesignProperties } from './design/cssProperties';
import { wsService } from './utils/websocketService';

installDesignProperties(document.documentElement);

const app = createApp(App);

const websocketUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:18005';
wsService.connect(resolveWebsocketUrl(websocketUrl, window.location.href));

app.use(router).use(createPinia()).mount('#app');
