import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig, loadEnv } from 'vite';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = { ...process.env, ...loadEnv(mode, process.cwd(), '') };

  const dataAccessorTarget =
    env.VITE_PROXY_DATA_ACCESSOR_TARGET ||
    `http://${env.DATABASE_ACCESSOR_HOST || 'database-accessor-api'}:${env.DATABASE_ACCESSOR_PORT || '8000'}`;

  const indicatorTarget =
    env.VITE_PROXY_INDICATOR_TARGET ||
    `http://${env.INDICATOR_API_HOST || 'indicator-api'}:${env.INDICATOR_API_PORT || '8010'}`;

  return {
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
      port: Number(env.FRONTEND_PORT || 5173),
      proxy: {
        "/api/data-accessor": {
          target: dataAccessorTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/data-accessor/, ''),
        },
        "/api/indicator-api": {
          target: indicatorTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/indicator-api/, ''),
        },
      },
    },
  };
});
