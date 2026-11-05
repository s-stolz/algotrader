import { onTestFinished, vi } from 'vitest';
import { wsService } from '@/utils/websocketService';
import type { BacktestEventMessage } from '@/types/backtestEventContracts';

let socket: TestSocket;
class TestSocket {
  static OPEN = 1;
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  constructor() {
    socket = this;
  }
  send() {}
  close() {
    this.onclose?.(new Event('close') as CloseEvent);
  }
}

export function installBacktestSocket() {
  wsService.close();
  vi.stubGlobal('WebSocket', TestSocket);
  wsService.connect('ws://backtest.test');
  socket.onopen?.();
  emitBacktestEvent({ type: 'backtestConnection', connected: true });
  onTestFinished(() => {
    wsService.close();
    vi.unstubAllGlobals();
  });
}

export function emitBacktestEvent(message: BacktestEventMessage) {
  socket.onmessage?.(
    new MessageEvent('message', { data: JSON.stringify(message) }),
  );
}

export function emitBacktestChange() {
  emitBacktestEvent({ type: 'backtestChanged' });
}
