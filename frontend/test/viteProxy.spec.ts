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
    expect(
      backtesterProxy.rewrite?.('/api/backtester/backtests/run-123/trades'),
    ).toBe('/backtests/run-123/trades');
  });

  it('derives the default backtester target from API host and port env', () => {
    const proxy = createDevServerProxy({
      BACKTESTER_API_HOST: 'backtester-api',
      BACKTESTER_API_PORT: '8020',
    });

    expect(proxy['/api/backtester'].target).toBe('http://backtester-api:8020');
  });
  it('routes broker discovery and history requests through their service proxies', () => {
    const proxy = createDevServerProxy({});
    expect(proxy['/api/broker'].target).toBe('http://broker-service:8050');
    expect(proxy['/api/ingestion'].target).toBe(
      'http://ingestion-service:8000',
    );
    expect(proxy['/api/broker'].rewrite?.('/api/broker/connection')).toBe(
      '/connection',
    );
    expect(
      proxy['/api/ingestion'].rewrite?.('/api/ingestion/history-downloads'),
    ).toBe('/history-downloads');
  });
});
