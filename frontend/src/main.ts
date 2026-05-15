import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { wsService } from './utils/websocketService';

const app = createApp(App);

const websocketUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8765';
wsService.connect(websocketUrl);

app
  .use(router)
  .use(createPinia())
  .mount('#app');
