import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;

  readonly url: string;
  readyState = MockWebSocket.CONNECTING;
  sentMessages: string[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    mockSockets.push(this);
  }

  send(message: string) {
    this.sentMessages.push(message);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new Event('close') as CloseEvent);
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  receive(data: string) {
    this.onmessage?.({ data } as MessageEvent<string>);
  }

  fail(event = new Event('error')) {
    this.onerror?.(event);
  }
}

let mockSockets: MockWebSocket[] = [];

const loadService = async () => {
  vi.resetModules();
  return import('@/utils/websocketService');
};

describe('WebSocket service', () => {
  beforeEach(() => {
    mockSockets = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('waits for readiness before sending JSON payloads', async () => {
    const { wsService } = await loadService();

    const readyHandler = vi.fn();
    wsService.on('ready', readyHandler);
    wsService.connect('ws://example.test');

    const [socket] = mockSockets;
    const sendPromise = wsService.send('subscribeCandles', {
      symbol: 'EURUSD',
      timeframe: 'M1',
    });

    expect(socket.sentMessages).toEqual([]);

    socket.open();
    await sendPromise;

    expect(readyHandler).toHaveBeenCalledTimes(1);
    expect(socket.sentMessages).toEqual([
      JSON.stringify({
        type: 'subscribeCandles',
        symbol: 'EURUSD',
        timeframe: 'M1',
      }),
    ]);
  });

  it('dispatches only validated inbound candle and indicator updates', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { wsService } = await loadService();

    const readyHandler = vi.fn();
    const candleHandler = vi.fn();
    const indicatorHandler = vi.fn();

    wsService.on('ready', readyHandler);
    wsService.on('candleUpdate', candleHandler);
    wsService.on('indicatorUpdate', indicatorHandler);
    wsService.connect('ws://example.test');

    const [socket] = mockSockets;
    socket.open();

    socket.receive(JSON.stringify({
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M1',
      timestamp_ms: 1_700_000_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      volume: 10,
    }));
    socket.receive(JSON.stringify({
      type: 'indicatorUpdate',
      clientIndicatorId: 'client-1',
      timestamp_ms: 1_700_000_000_000,
      values: { sma: 1.2, signal: null },
    }));

    socket.receive(JSON.stringify({ type: 'candleUpdate', symbol: 'EURUSD' }));
    socket.receive(JSON.stringify({ type: 'indicatorUpdate', clientIndicatorId: 'client-1' }));
    socket.receive(JSON.stringify({ type: 'ready' }));

    expect(() => socket.receive('not json')).not.toThrow();

    expect(readyHandler).toHaveBeenCalledTimes(1);
    expect(candleHandler).toHaveBeenCalledOnce();
    expect(candleHandler).toHaveBeenCalledWith({
      type: 'candleUpdate',
      symbol: 'EURUSD',
      timeframe: 'M1',
      timestamp_ms: 1_700_000_000_000,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      volume: 10,
    });
    expect(indicatorHandler).toHaveBeenCalledOnce();
    expect(indicatorHandler).toHaveBeenCalledWith({
      type: 'indicatorUpdate',
      clientIndicatorId: 'client-1',
      timestamp_ms: 1_700_000_000_000,
      values: { sma: 1.2, signal: null },
    });
    expect(warn).toHaveBeenCalled();
  });

  it('accepts server acknowledgements without warning or update dispatch', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { wsService } = await loadService();

    const candleHandler = vi.fn();
    const indicatorHandler = vi.fn();

    wsService.on('candleUpdate', candleHandler);
    wsService.on('indicatorUpdate', indicatorHandler);
    wsService.connect('ws://example.test');

    const [socket] = mockSockets;
    socket.open();

    socket.receive(JSON.stringify({
      type: 'subscribed',
      symbol: 'EURUSD',
      timeframe: 'M1',
    }));
    socket.receive(JSON.stringify({
      type: 'indicatorSubscribed',
      symbol: 'EURUSD',
      timeframe: 'M1',
      indicatorId: 1,
      clientIndicatorId: 'client-1',
      streamId: null,
    }));
    socket.receive(JSON.stringify({
      type: 'indicatorUnsubscribed',
      symbol: 'EURUSD',
      timeframe: 'M1',
      indicatorId: 1,
      clientIndicatorId: 'client-1',
    }));

    expect(warn).not.toHaveBeenCalled();
    expect(candleHandler).not.toHaveBeenCalled();
    expect(indicatorHandler).not.toHaveBeenCalled();
  });

  it('emits server error messages without classifying them as invalid', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { wsService } = await loadService();

    const serverErrorHandler = vi.fn();

    wsService.on('serverError', serverErrorHandler);
    wsService.connect('ws://example.test');

    const [socket] = mockSockets;
    socket.open();

    socket.receive(JSON.stringify({
      type: 'error',
      error: 'Missing symbol or timeframe',
    }));

    expect(warn).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith('WebSocket server error:', 'Missing symbol or timeframe');
    expect(serverErrorHandler).toHaveBeenCalledWith({
      type: 'error',
      error: 'Missing symbol or timeframe',
    });
  });

  it('forwards errors, removes listeners, and emits disconnect on close', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { wsService } = await loadService();

    const errorHandler = vi.fn();
    const disconnectedHandler = vi.fn();
    const removedHandler = vi.fn();

    wsService.on('error', errorHandler);
    wsService.on('disconnected', disconnectedHandler);
    wsService.on('disconnected', removedHandler);
    wsService.off('disconnected', removedHandler);
    wsService.connect('ws://example.test');

    const [socket] = mockSockets;
    const errorEvent = new Event('error');
    socket.fail(errorEvent);
    wsService.close();

    expect(errorHandler).toHaveBeenCalledWith(errorEvent);
    expect(disconnectedHandler).toHaveBeenCalledOnce();
    expect(removedHandler).not.toHaveBeenCalled();
    expect(socket.readyState).toBe(MockWebSocket.CLOSED);
  });
});
