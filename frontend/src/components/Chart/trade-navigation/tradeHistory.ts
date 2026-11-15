import { ChartRecovery, type ChartRecoveryAdapter } from '../chartRecovery';
import { timeframeToMinutes } from '@/utils/timeframes';
import type { CandleUpdateMessage, ChartCandle } from '@/types/contracts';
import type { ChartSessionKey } from '../chartSession';

export interface ChartSessionOlderHistorySignal {
  barsBefore: number;
  barsAfter?: number;
  nowMs: number;
  scrollToRealtime?: boolean;
}

export interface TradeHistoryAdapter {
  prepare(): void;
  getRange(): ChartSessionOlderHistorySignal | null;
  fetchBefore(
    key: ChartSessionKey,
    endMs: number,
    limit: number,
    signal: AbortSignal,
  ): Promise<ChartCandle[]>;
  fetchAfter(
    key: ChartSessionKey,
    startMs: number,
    signal: AbortSignal,
  ): Promise<ChartCandle[]>;
  install(candles: readonly ChartCandle[], targetMs: number | null): void;
  initializeIndicators(key: ChartSessionKey): Promise<void>;
  extendIndicators(
    key: ChartSessionKey,
    candles: readonly ChartCandle[],
    signal: AbortSignal,
  ): Promise<void>;
  historical(value: boolean): void;
  resumeLive(key: ChartSessionKey): void;
  loading(value: boolean): void;
}

export class TradeHistory {
  onPresent:
    | ((timestamp: number | null, live: readonly CandleUpdateMessage[]) => void)
    | null = null;
  private liveTail = new Map<number, CandleUpdateMessage>();
  lastTimestamp: number | null = null;
  private firstTimestamp: number | null = null;
  private controller: AbortController | null = null;
  private key: ChartSessionKey | null = null;
  private busy = false;
  private historical = false;
  private olderExhausted = false;
  private olderRequested = false;
  private newerRequested = false;
  private range: ChartSessionOlderHistorySignal | null = null;

  constructor(private readonly adapter: TradeHistoryAdapter) {}

  getVisibleRange(): ChartSessionOlderHistorySignal | null {
    return this.adapter.getRange();
  }

  get blocksOlderHistory() {
    return this.historical;
  }
  receive(message: CandleUpdateMessage): boolean {
    if (!this.historical) return false;
    this.liveTail.set(message.timestamp_ms, { ...message });
    if (this.liveTail.size > 3)
      this.liveTail.delete(Math.min(...this.liveTail.keys()));
    return true;
  }

  cancel(): void {
    this.liveTail.clear();
    this.controller?.abort();
    this.controller = null;
    this.key = null;
    this.busy = false;
    this.historical = false;
    this.range = null;
    this.olderRequested = this.newerRequested = false;
    this.adapter.historical(false);
    this.adapter.loading(false);
  }

  async load(key: ChartSessionKey, timestampMs: number): Promise<boolean> {
    this.cancel();
    this.key = key;
    this.controller = new AbortController();
    const { signal } = this.controller;
    this.historical = true;
    this.olderExhausted = false;
    this.firstTimestamp = this.lastTimestamp = null;
    this.adapter.historical(true);
    this.adapter.prepare();
    this.setBusy(true);
    try {
      const before = await this.adapter.fetchBefore(
        key,
        timestampMs + 1,
        11,
        signal,
      );
      signal.throwIfAborted();
      const target = before.at(-1);
      if (!target) throw new Error('Trade candle is unavailable');
      const after = await this.adapter.fetchAfter(
        key,
        target.timestamp_ms,
        signal,
      );
      signal.throwIfAborted();
      if (after[0]?.timestamp_ms !== target.timestamp_ms)
        throw new Error('Trade candle is unavailable');
      const candles = [...before.slice(0, -1), ...after];
      this.firstTimestamp = candles[0].timestamp_ms;
      this.lastTimestamp = candles.at(-1)!.timestamp_ms;
      this.adapter.install(candles, timestampMs);
      this.range ??= this.adapter.getRange();
      await this.adapter.initializeIndicators(key);
      signal.throwIfAborted();
      if (after.length < 500) this.reachedPresent();
      this.setBusy(false);
      await this.drainPages();
      return true;
    } catch (error) {
      if (!signal.aborted)
        console.error('Failed to load trade history:', error);
      return false;
    } finally {
      if (!signal.aborted) this.setBusy(false);
    }
  }

  requestHistory(range: ChartSessionOlderHistorySignal): boolean {
    if (!this.historical) return false;
    void this.requestPage(range);
    return true;
  }

  async requestPage(range: ChartSessionOlderHistorySignal): Promise<void> {
    const previous = this.range;
    this.range = range;
    if (previous) {
      const older = range.barsBefore < previous.barsBefore;
      const newer =
        range.barsAfter !== undefined &&
        previous.barsAfter !== undefined &&
        range.barsAfter < previous.barsAfter;
      if (older || newer) {
        this.olderRequested = older && range.barsBefore < 100;
        this.newerRequested = newer && range.barsAfter! < 100;
      }
    }
    await this.drainPages();
  }

  private async drainPages(): Promise<void> {
    if (!this.historical || this.busy || !this.key || !this.controller) return;
    const { signal } = this.controller;
    const key = this.key;
    this.setBusy(true);
    try {
      while (!signal.aborted && this.historical && this.range) {
        const older =
          this.olderRequested &&
          !this.olderExhausted &&
          this.range.barsBefore < 100;
        const newer =
          this.newerRequested &&
          this.range.barsAfter !== undefined &&
          this.range.barsAfter < 100;
        if (
          (!older && !newer) ||
          this.firstTimestamp === null ||
          this.lastTimestamp === null
        )
          break;
        const candles = older
          ? await this.adapter.fetchBefore(
              key,
              this.firstTimestamp,
              500,
              signal,
            )
          : await this.adapter.fetchAfter(
              key,
              this.lastTimestamp + timeframeToMinutes(key.timeframe) * 60_000,
              signal,
            );
        signal.throwIfAborted();
        if (candles.length) {
          const first = Math.min(this.firstTimestamp, candles[0].timestamp_ms);
          const last = Math.max(
            this.lastTimestamp,
            candles.at(-1)!.timestamp_ms,
          );
          if (first === this.firstTimestamp && last === this.lastTimestamp)
            throw new Error('History page did not extend candle coverage');
          this.firstTimestamp = first;
          this.lastTimestamp = last;
          // Account for the page before render callbacks report the updated range.
          if (older) this.range.barsBefore += candles.length;
          else if (this.range.barsAfter !== undefined)
            this.range.barsAfter += candles.length;
          this.adapter.install(candles, null);
          await this.adapter.extendIndicators(key, candles, signal);
          signal.throwIfAborted();
        }
        this.range = this.adapter.getRange() ?? this.range;
        if (older) this.olderExhausted = candles.length < 500;
        else if (candles.length < 500) this.reachedPresent();
      }
    } catch (error) {
      if (!signal.aborted) {
        this.olderRequested = this.newerRequested = false;
        console.error('Failed to page trade history:', error);
      }
    } finally {
      if (!signal.aborted) this.setBusy(false);
    }
  }

  private reachedPresent() {
    this.historical = false;
    this.adapter.historical(false);
    if (this.key) this.adapter.resumeLive(this.key);
    const live = [...this.liveTail.values()].sort(
      (a, b) => a.timestamp_ms - b.timestamp_ms,
    );
    this.liveTail.clear();
    this.onPresent?.(this.lastTimestamp, live);
  }
  private setBusy(value: boolean) {
    this.busy = value;
    this.adapter.loading(value);
  }
}

export function createHistoryRecovery(
  options: { recovery: ChartRecoveryAdapter; tradeHistory?: TradeHistory },
  getKey: () => ChartSessionKey | null,
): ChartRecovery {
  const recovery = new ChartRecovery(options.recovery);
  const history = options.tradeHistory;
  if (history)
    history.onPresent = (timestamp, live) => {
      const key = getKey();
      if (!key) return;
      recovery.start(key);
      recovery.catchUp(timestamp, live);
    };
  return recovery;
}
