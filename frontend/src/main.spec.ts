import { beforeEach, describe, expect, it, vi } from 'vitest';

const bootstrapMock = vi.hoisted(() => {
  const app = {
    config: {
      globalProperties: {} as Record<string, unknown>,
    },
    use: vi.fn(),
    mount: vi.fn(),
  };
  app.use.mockReturnValue(app);

  return {
    app,
    connect: vi.fn(),
    createApp: vi.fn(() => app),
    createPinia: vi.fn(() => ({ name: 'pinia' })),
    router: { name: 'router' },
  };
});

vi.mock('vue', () => ({
  createApp: bootstrapMock.createApp,
}));

vi.mock('pinia', () => ({
  createPinia: bootstrapMock.createPinia,
}));

vi.mock('./App.vue', () => ({
  default: { name: 'MockApp' },
}));

vi.mock('./router', () => ({
  default: bootstrapMock.router,
}));

vi.mock('./utils/websocketService', () => ({
  wsService: {
    connect: bootstrapMock.connect,
  },
}));

describe('frontend bootstrap', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    bootstrapMock.app.config.globalProperties = {};
    bootstrapMock.app.use.mockClear();
    bootstrapMock.app.mount.mockClear();
    bootstrapMock.app.use.mockReturnValue(bootstrapMock.app);
    bootstrapMock.connect.mockClear();
    bootstrapMock.createApp.mockClear();
    bootstrapMock.createPinia.mockClear();
  });

  it('connects to the default WebSocket URL, installs app plugins, and mounts without globals', async () => {
    vi.stubEnv('VITE_WS_URL', '');

    await import('./main');

    expect(bootstrapMock.connect).toHaveBeenCalledWith('ws://localhost:8765');
    expect(bootstrapMock.app.use).toHaveBeenCalledWith(bootstrapMock.router);
    expect(bootstrapMock.createPinia).toHaveBeenCalledOnce();
    expect(bootstrapMock.app.use).toHaveBeenCalledWith({ name: 'pinia' });
    expect(bootstrapMock.app.mount).toHaveBeenCalledWith('#app');
    expect(bootstrapMock.app.config.globalProperties).not.toHaveProperty('$wss');
  });

  it('uses the configured WebSocket URL when provided', async () => {
    vi.stubEnv('VITE_WS_URL', 'ws://configured.example.test');

    await import('./main');

    expect(bootstrapMock.connect).toHaveBeenCalledWith('ws://configured.example.test');
  });
});
