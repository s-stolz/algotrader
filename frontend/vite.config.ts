import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

import { createDevServerProxy } from './src/viteProxy';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = { ...process.env, ...loadEnv(mode, process.cwd(), '') };

  return {
    plugins: [
      vue(),
      ...(mode === 'navigation-prototype' ? [{
        name: 'navigation-prototype-read-only',
        configureServer(server: import('vite').ViteDevServer) {
          server.middlewares.use((request, response, next) => {
            if (request.url?.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(request.method || 'GET')) {
              response.statusCode = 403;
              response.setHeader('Content-Type', 'application/json');
              response.end(JSON.stringify({ detail: 'Navigation prototype: writes are disabled.' }));
              return;
            }
            next();
          });
        },
      }] : []),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '0.0.0.0',
      port: Number(env.FRONTEND_PORT || 5173),
      proxy: createDevServerProxy(env),
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./test/setup.ts'],
      include: ['test/**/*.{test,spec}.ts'],
    },
  };
});
