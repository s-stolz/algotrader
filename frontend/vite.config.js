import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  publicPath: "",
  server: {
    host: '0.0.0.0',
    proxy: {
      "/api/data-accessor": {
        target: "http://database-accessor-api:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/data-accessor/, ''),
      },
      "/api/indicator-api": {
        target: "http://indicator-api:8010",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/indicator-api/, ''),
      },
    },
  },
});
