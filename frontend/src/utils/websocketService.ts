import mitt, { type Emitter, type EventType, type Handler } from 'mitt';

import {
  isWebSocketInboundMessage,
  type CandleUpdateMessage,
  type IndicatorUpdateMessage,
  type JsonValue,
  type WebSocketErrorMessage,
  type WebSocketInboundMessage,
} from '@/types/contracts';

export interface WebSocketServiceEventMap {
  ready: undefined;
  error: Event;
  disconnected: CloseEvent | Event;
  candleUpdate: CandleUpdateMessage;
  indicatorUpdate: IndicatorUpdateMessage;
  serverError: WebSocketErrorMessage;
}

type MittEvents = WebSocketServiceEventMap & Record<EventType, unknown>;
type WebSocketServiceEventName = keyof WebSocketServiceEventMap;

export type WebSocketSendPayload = Record<string, JsonValue | undefined>;
export type WebSocketEventHandler<EventName extends WebSocketServiceEventName> = Handler<
  WebSocketServiceEventMap[EventName]
>;

function parseInboundMessage(data: MessageEvent['data']): WebSocketInboundMessage | null {
  if (typeof data !== 'string') {
    console.warn('Ignoring non-text WebSocket message:', data);
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch (error) {
    console.warn('Ignoring malformed WebSocket message:', error);
    return null;
  }

  if (isWebSocketInboundMessage(parsed)) {
    return parsed;
  }

  console.warn('Ignoring invalid WebSocket message:', parsed);
  return null;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private isReady = false;
  private readyPromise: Promise<void> | null = null;
  private readyResolve: (() => void) | null = null;
  private readonly emitter: Emitter<MittEvents>;

  constructor(emitter: Emitter<MittEvents> = mitt<MittEvents>()) {
    this.emitter = emitter;
  }

  connect(url: string): void {
    this.isReady = false;
    this.readyPromise = new Promise<void>((resolve) => {
      this.readyResolve = resolve;
    });

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.isReady = true;
      this.emit('ready', undefined);
      this.readyResolve?.();
      this.readyResolve = null;
    };

    this.ws.onmessage = (event) => {
      const message = parseInboundMessage(event.data);
      if (!message) {
        return;
      }

      switch (message.type) {
        case 'candleUpdate':
          this.emit('candleUpdate', message);
          return;
        case 'indicatorUpdate':
          this.emit('indicatorUpdate', message);
          return;
        case 'error':
          console.error('WebSocket server error:', message.error);
          this.emit('serverError', message);
          return;
        default:
          return;
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    };

    this.ws.onclose = (event) => {
      this.isReady = false;
      this.emit('disconnected', event);
    };
  }

  async waitUntilReady(): Promise<void> {
    if (this.isReady) {
      return;
    }

    if (this.readyPromise) {
      await this.readyPromise;
    }
  }

  async send(type: string, data: WebSocketSendPayload = {}): Promise<void> {
    await this.waitUntilReady();

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, ...data }));
    }
  }

  close(): void {
    this.ws?.close();
  }

  on<EventName extends WebSocketServiceEventName>(
    event: EventName,
    callback: WebSocketEventHandler<EventName>,
  ): void {
    this.emitter.on(event, callback as Handler<MittEvents[EventName]>);
  }

  off<EventName extends WebSocketServiceEventName>(
    event: EventName,
    callback: WebSocketEventHandler<EventName>,
  ): void {
    this.emitter.off(event, callback as Handler<MittEvents[EventName]>);
  }

  private emit<EventName extends WebSocketServiceEventName>(
    event: EventName,
    payload: WebSocketServiceEventMap[EventName],
  ): void {
    this.emitter.emit(event, payload as MittEvents[EventName]);
  }
}

export const wsService = new WebSocketService();
