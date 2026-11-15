import type {
  HistoryDownloadChanged,
  HistoryDownloadsConnection,
} from '@/types/historyDownloadContracts';
import { BACKTEST_PROGRESS_STAGES } from '@/types/backtestEventContracts';
import type {
  BacktestChangedMessage,
  BacktestConnectionMessage,
  BacktestHealthMessage,
  BacktestProgressMessage,
} from '@/types/backtestEventContracts';
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
  historyDownloadChanged: HistoryDownloadChanged;
  historyDownloadsConnection: HistoryDownloadsConnection;
  backtestChanged: BacktestChangedMessage;
  backtestConnection: BacktestConnectionMessage;
  backtestHealth: BacktestHealthMessage;
  backtestProgress: BacktestProgressMessage;
  error: Event;
  disconnected: CloseEvent | Event;
  candleUpdate: CandleUpdateMessage;
  indicatorUpdate: IndicatorUpdateMessage;
  serverError: WebSocketErrorMessage;
}

type MittEvents = WebSocketServiceEventMap & Record<EventType, unknown>;
type WebSocketServiceEventName = keyof WebSocketServiceEventMap;

export type WebSocketSendPayload = Record<string, JsonValue | undefined>;
export type WebSocketEventHandler<EventName extends WebSocketServiceEventName> =
  Handler<WebSocketServiceEventMap[EventName]>;

function parseInboundMessage(
  data: MessageEvent['data'],
): WebSocketInboundMessage | null {
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
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  private retryDelay = 500;
  private subscriptions = new Map<string, string>();
  backtestsConnected = false;
  readonly backtestProgress = new Map<string, BacktestProgressMessage>();
  private isReady = false;
  private readyPromise: Promise<void> | null = null;
  private readyResolve: (() => void) | null = null;
  private readonly emitter: Emitter<MittEvents>;

  constructor(emitter: Emitter<MittEvents> = mitt<MittEvents>()) {
    this.emitter = emitter;
  }

  connect(url: string): void {
    this.stopped = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    const previous = this.ws;
    this.ws = null;
    previous?.close();
    this.isReady = false;
    this.backtestsConnected = false;
    if (!this.readyResolve) {
      this.readyPromise = new Promise<void>((resolve) => {
        this.readyResolve = resolve;
      });
    }
    const socket = new WebSocket(url);
    this.ws = socket;

    socket.onopen = () => {
      if (this.ws !== socket) return;
      this.isReady = true;
      this.retryDelay = 500;
      for (const message of this.subscriptions.values()) socket.send(message);
      this.emit('ready', undefined);
      this.readyResolve?.();
      this.readyResolve = null;
    };

    socket.onmessage = (event) => {
      if (this.ws !== socket) return;
      const message = parseInboundMessage(event.data);
      if (!message) {
        return;
      }

      switch (message.type) {
        case 'historyDownloadChanged':
          this.emit('historyDownloadChanged', message);
          return;
        case 'historyDownloadsConnection':
          this.emit('historyDownloadsConnection', message);
          return;
        case 'backtestConnection':
          this.backtestsConnected = message.connected;
          this.emit('backtestConnection', message);
          return;
        case 'backtestChanged':
          this.emit('backtestChanged', message);
          return;
        case 'backtestProgress': {
          const previous = this.backtestProgress.get(message.run_id);
          // Snapshot restoration can race a newer streamed stage.
          if (
            previous &&
            (BACKTEST_PROGRESS_STAGES.indexOf(previous.stage) >
              BACKTEST_PROGRESS_STAGES.indexOf(message.stage) ||
              (previous.stage === message.stage &&
                ((message.processed_candles ?? -1) <=
                  (previous.processed_candles ?? -1) ||
                  (previous.total_candles !== undefined &&
                    message.total_candles !== previous.total_candles))))
          )
            return;
          const progress = { ...previous, ...message };
          this.backtestProgress.set(message.run_id, progress);
          if (this.backtestProgress.size > 64) {
            const oldest = this.backtestProgress.keys().next().value;
            if (oldest !== undefined) this.backtestProgress.delete(oldest);
          }
          this.emit('backtestProgress', progress);
          return;
        }
        case 'backtestHealth':
          this.emit('backtestHealth', message);
          return;
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

    socket.onerror = (error) => {
      if (this.ws !== socket) return;
      console.error('WebSocket error:', error);
      this.emit('error', error);
    };

    socket.onclose = (event) => {
      if (this.ws !== socket) return;
      this.isReady = false;
      this.backtestsConnected = false;
      this.emit('disconnected', event);
      if (!this.stopped) {
        this.reconnectTimer = setTimeout(
          () => this.connect(url),
          this.retryDelay,
        );
        this.retryDelay = Math.min(this.retryDelay * 2, 10000);
      }
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
    const payload = JSON.stringify({ type, ...data });
    const key = subscriptionKey(type, data);
    if (key !== null) {
      if (type.startsWith('unsubscribe')) this.subscriptions.delete(key);
      else this.subscriptions.set(key, payload);
      // Desired subscriptions are replayed on open, including changes made offline.
      if (!this.isReady) return;
    } else {
      await this.waitUntilReady();
    }
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(payload);
  }

  close(): void {
    this.backtestProgress.clear();
    this.stopped = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
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

function subscriptionKey(
  type: string,
  data: WebSocketSendPayload,
): string | null {
  const topic = type.replace(/^(un)?subscribe/, '');
  if (topic === type) return null;
  if (topic === 'Backtests') return topic;
  if (topic === 'HistoryDownloads') return `${topic}:${data.market_id}`;
  if (topic === 'Candles')
    return `${topic}:${data.market_id}:${data.timeframe}`;
  if (topic === 'Indicator')
    return `${topic}:${data.market_id}:${data.clientIndicatorId}`;
  return null;
}

export const wsService = new WebSocketService();
