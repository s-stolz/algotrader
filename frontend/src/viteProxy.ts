import type { ProxyOptions } from 'vite';

type DevServerEnv = Record<string, string | undefined>;

function serviceTarget(
  env: DevServerEnv,
  explicitKey: string,
  hostKey: string,
  fallbackHost: string,
  portKey: string,
  fallbackPort: string,
): string {
  return env[explicitKey] || `http://${env[hostKey] || fallbackHost}:${env[portKey] || fallbackPort}`;
}

export function createDevServerProxy(env: DevServerEnv): Record<string, ProxyOptions> {
  return {
    '/api/data-accessor': {
      target: serviceTarget(
        env,
        'VITE_PROXY_DATA_ACCESSOR_TARGET',
        'DATABASE_ACCESSOR_HOST',
        'database-accessor-api',
        'DATABASE_ACCESSOR_PORT',
        '8000',
      ),
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api\/data-accessor/, ''),
    },
    '/api/backtester': {
      target: serviceTarget(
        env,
        'VITE_PROXY_BACKTESTER_TARGET',
        'BACKTESTER_API_HOST',
        'backtester-api',
        'BACKTESTER_API_PORT',
        '8020',
      ),
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api\/backtester/, ''),
    },
    '/api/indicator-api': {
      target: serviceTarget(
        env,
        'VITE_PROXY_INDICATOR_TARGET',
        'INDICATOR_API_HOST',
        'indicator-api',
        'INDICATOR_API_PORT',
        '8010',
      ),
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api\/indicator-api/, ''),
    },
  };
}
