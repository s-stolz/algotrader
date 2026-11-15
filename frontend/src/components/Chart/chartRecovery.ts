import type { ChartRecoveryQuery } from '@/types/chartRecovery';
import type { CandleUpdateMessage, ChartCandle } from '@/types/contracts';
import type { ChartSessionKey } from './chartSession';

type ConnectionEvent = 'ready' | 'disconnected';
export interface ChartRecoveryAdapter {
  on(event: ConnectionEvent, handler: () => void): void;
  off(event: ConnectionEvent, handler: () => void): void;
  lastTimestamp(): number | null;
  fetch(query: ChartRecoveryQuery): Promise<ChartCandle[]>;
  merge(
    candles: readonly ChartCandle[],
    live: readonly CandleUpdateMessage[],
  ): void;
  recoverIndicators(
    query: ChartRecoveryQuery,
    isCurrent: () => boolean,
    signal: AbortSignal,
  ): Promise<void>;
}

// Each session owns its listeners and unresolved inclusive recovery anchor.
export class ChartRecovery {
  private controller: AbortController | null = null;
  private key: ChartSessionKey | null = null;
  private anchor: number | null = null;
  private loaded = false;
  private disconnectedAt: number | null = null;
  private pending = false;
  private revision = 0;
  private live: Map<number, CandleUpdateMessage> | null = null;

  constructor(private readonly adapter: ChartRecoveryAdapter) {}

  start(key: ChartSessionKey): void {
    this.stop();
    this.key = key;
    this.adapter.on('disconnected', this.disconnect);
    this.adapter.on('ready', this.ready);
  }

  stop(): void {
    this.adapter.off('disconnected', this.disconnect);
    this.adapter.off('ready', this.ready);
    this.controller?.abort();
    this.revision += 1;
    this.key = null;
    this.anchor = null;
    this.loaded = false;
    this.pending = false;
    this.disconnectedAt = null;
    this.live = null;
  }

  historyLoaded(lastTimestamp: number | null): void {
    this.loaded = true;
    if (this.disconnectedAt !== null && this.anchor === null) {
      this.anchor = lastTimestamp ?? this.disconnectedAt;
    }
    if (this.pending) this.ready();
  }

  record(message: CandleUpdateMessage): void {
    this.live?.set(message.timestamp_ms, { ...message });
  }

  private disconnect = (): void => {
    this.controller?.abort();
    this.revision += 1;
    this.live = null;
    this.pending = false;
    this.disconnectedAt ??= Date.now();
    if (this.loaded) {
      this.anchor ??= this.adapter.lastTimestamp() ?? this.disconnectedAt;
    }
  };

  private ready = (): void => {
    if (!this.key || this.disconnectedAt === null) return;
    if (!this.loaded) {
      this.pending = true;
      return;
    }
    this.pending = false;
    const startMs = this.anchor;
    if (startMs === null) return;
    this.controller?.abort();
    this.controller = new AbortController();
    const revision = ++this.revision;
    const isCurrent = () => revision === this.revision && this.key !== null;
    const live = new Map<number, CandleUpdateMessage>();
    this.live = live;
    const key = this.key;
    const endMs = Math.max(Date.now(), startMs + 1);
    void this.recover(
      { ...key, startMs, endMs },
      live,
      isCurrent,
      this.controller.signal,
    );
  };

  private async recover(
    query: ChartRecoveryQuery,
    live: Map<number, CandleUpdateMessage>,
    isCurrent: () => boolean,
    signal: AbortSignal,
  ): Promise<void> {
    const results = await Promise.allSettled([
      this.adapter.fetch(query).then((candles) => {
        if (isCurrent()) this.adapter.merge(candles, [...live.values()]);
      }),
      this.adapter.recoverIndicators(query, isCurrent, signal),
    ]);
    if (!isCurrent()) return;
    this.live = null;
    const failures = results.filter((result) => result.status === 'rejected');
    if (failures.length) {
      console.error(
        'Failed to recover chart history after reconnect:',
        failures,
      );
      return;
    }
    this.anchor = null;
    this.disconnectedAt = null;
  }
}
