import "./assets/main.css";

import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import { wsService } from "./utils/websocketService";

const app = createApp(App);

// Initialize the WebSocket globally
wsService.connect("ws://localhost:8765");
app.config.globalProperties.$wss = wsService;

app.use(router).use(createPinia()).mount("#app");
