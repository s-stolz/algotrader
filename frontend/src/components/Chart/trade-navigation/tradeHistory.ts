import type { CandleUpdateMessage, ChartCandle } from '@/types/contracts';
import type { ChartSessionKey } from '../chartSession';

export interface TradeHistoryAdapter {
  prepare(): void;
  fetchBefore(
    key: ChartSessionKey,
    timestampMs: number,
    signal: AbortSignal,
  ): Promise<ChartCandle[]>;
  stream(
    key: ChartSessionKey,
    startMs: number,
    endMs: number,
    signal: AbortSignal,
    onBatch: (candles: ChartCandle[]) => Promise<void>,
  ): Promise<void>;
  append(
    candles: readonly ChartCandle[],
    targetMs: number | null,
  ): void | Promise<void>;
  initializeIndicators(key: ChartSessionKey): Promise<void>;
  extendIndicators(
    key: ChartSessionKey,
    candles: readonly ChartCandle[],
    signal: AbortSignal,
  ): Promise<void>;
  waitForInteraction?(): Promise<void>;
  finish(live: readonly CandleUpdateMessage[]): void;
  cancel(hold?: boolean): void;
  loading(value: boolean): void;
}

// The received prefix is usable chart history, but is never treated as caught up
// until the stream explicitly completes. Live candles stay separate until then.
export class TradeHistory {
  lastTimestamp: number | null = null;
  private controller: AbortController | null = null;
  private live = new Map<number, CandleUpdateMessage>();
  private holdingLive = false;

  constructor(private readonly adapter: TradeHistoryAdapter) {}

  get blocksOlderHistory(): boolean {
    return this.holdingLive;
  }

  receive(message: CandleUpdateMessage): boolean {
    if (!this.holdingLive) return false;
    if (this.controller && !this.controller.signal.aborted)
      this.live.set(message.timestamp_ms, { ...message });
    return true;
  }

  cancel(hold = false): void {
    this.controller?.abort();
    this.controller = null;
    this.live.clear();
    this.holdingLive = hold;
    this.adapter.cancel(hold);
    this.adapter.loading(false);
  }

  async load(key: ChartSessionKey, timestampMs: number): Promise<boolean> {
    this.cancel();
    this.lastTimestamp = null;
    const controller = new AbortController();
    this.controller = controller;
    const { signal } = controller;
    this.holdingLive = true;
    this.adapter.prepare();
    this.adapter.loading(true);
    let indicatorWork = Promise.resolve();
    let indicatorFailure: unknown = null;
    let initialized = false;
    const enqueue = (candles: readonly ChartCandle[]) => {
      indicatorWork = indicatorWork
        .then(async () => {
          signal.throwIfAborted();
          await this.adapter.extendIndicators(key, candles, signal);
        })
        .catch((error: unknown) => {
          indicatorFailure = error;
        });
    };
    try {
      const endMs = Date.now();
      const before = await this.adapter.fetchBefore(key, timestampMs, signal);
      signal.throwIfAborted();
      if (!before.length) throw new Error('Trade candle is unavailable');
      const target = before.at(-1)!;
      const pending = before.slice(0, -1);
      const install = async (candles: ChartCandle[]) => {
        signal.throwIfAborted();
        await this.adapter.append(candles, initialized ? null : timestampMs);
        signal.throwIfAborted();
        if (!initialized) {
          initialized = true;
          indicatorWork = this.adapter
            .initializeIndicators(key)
            .catch((error: unknown) => {
              indicatorFailure = error;
            });
        }
        enqueue(candles);
      };
      let receivedTarget = false;
      const consume = async (batch: ChartCandle[]) => {
        signal.throwIfAborted();
        if (!receivedTarget && batch.length) {
          if (batch[0].timestamp_ms !== target.timestamp_ms)
            throw new Error('Trade candle is unavailable');
          receivedTarget = true;
        }
        this.lastTimestamp = batch.at(-1)?.timestamp_ms ?? this.lastTimestamp;
        pending.push(...batch);
        while (pending.length >= 510) {
          await install(pending.splice(0, 510));
          await new Promise<void>((resolve) => setTimeout(resolve, 0));
          signal.throwIfAborted();
        }
      };
      await this.adapter.stream(
        key,
        target.timestamp_ms,
        endMs,
        signal,
        async (batch) => {
          // A range crossing the aggregate retention boundary can begin after the
          // known target. A separate prefix stream uses the accessor's raw fallback.
          if (!receivedTarget && batch[0]?.timestamp_ms > target.timestamp_ms) {
            await this.adapter.stream(
              key,
              target.timestamp_ms,
              batch[0].timestamp_ms,
              signal,
              consume,
            );
            signal.throwIfAborted();
            if (!receivedTarget) throw new Error('Trade candle is unavailable');
            if (pending.length) await install(pending.splice(0));
          }
          await consume(batch);
        },
      );
      signal.throwIfAborted();
      if (
        !initialized &&
        !pending.some((candle) => candle.timestamp_ms >= target.timestamp_ms)
      )
        throw new Error('Trade candle is unavailable');
      if (pending.length) await install(pending);
      await indicatorWork;
      signal.throwIfAborted();
      if (indicatorFailure)
        console.error('Failed to extend trade indicators:', indicatorFailure);
      await this.adapter.waitForInteraction?.();
      signal.throwIfAborted();
      this.adapter.finish(
        [...this.live.values()].sort((a, b) => a.timestamp_ms - b.timestamp_ms),
      );
      signal.throwIfAborted();
      this.live.clear();
      this.holdingLive = false;
      return true;
    } catch (error) {
      if (!signal.aborted) {
        console.error('Failed to load trade history:', error);
        this.adapter.cancel(true);
      }
      return false;
    } finally {
      if (this.controller === controller) {
        this.adapter.loading(false);
        controller.abort();
        this.live.clear();
      }
    }
  }
}
