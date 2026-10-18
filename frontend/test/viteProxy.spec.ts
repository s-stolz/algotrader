import { describe, expect, it } from 'vitest';

import { createDevServerProxy } from '@/viteProxy';

describe('Vite development proxy configuration', () => {
  it('proxies public backtester API calls to the backtester service', () => {
    const proxy = createDevServerProxy({
      VITE_PROXY_BACKTESTER_TARGET: 'http://backtester-api:8020',
    });
    const backtesterProxy = proxy['/api/backtester'];

    expect(backtesterProxy.target).toBe('http://backtester-api:8020');
    expect(backtesterProxy.changeOrigin).toBe(true);
    expect(backtesterProxy.rewrite?.('/api/backtester/backtests/run-123/trades')).toBe(
      '/backtests/run-123/trades',
    );
  });

  it('derives the default backtester target from API host and port env', () => {
    const proxy = createDevServerProxy({
      BACKTESTER_API_HOST: 'backtester-api',
      BACKTESTER_API_PORT: '8020',
    });

    expect(proxy['/api/backtester'].target).toBe('http://backtester-api:8020');
  });
});
