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
  loading(value: boolean): void;
}

export class TradeHistory {
  onPresent: ((timestamp: number | null) => void) | null = null;
  lastTimestamp: number | null = null;
  private firstTimestamp: number | null = null;
  private controller: AbortController | null = null;
  private key: ChartSessionKey | null = null;
  private busy = false;
  private historical = false;
  private olderExhausted = false;
  private range: ChartSessionOlderHistorySignal | null = null;

  constructor(private readonly adapter: TradeHistoryAdapter) {}

  get blocksOlderHistory() {
    return this.historical;
  }
  receive(_message: CandleUpdateMessage): boolean {
    return this.historical;
  }

  cancel(): void {
    this.controller?.abort();
    this.controller = null;
    this.key = null;
    this.busy = false;
    this.historical = false;
    this.range = null;
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
      await this.adapter.initializeIndicators(key);
      signal.throwIfAborted();
      if (after.length < 500) this.reachedPresent();
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
    if (
      !this.historical ||
      this.busy ||
      !this.key ||
      !this.controller ||
      !previous
    )
      return;
    const older =
      range.barsBefore < 100 &&
      range.barsBefore < previous.barsBefore &&
      !this.olderExhausted;
    const newer =
      range.barsAfter !== undefined &&
      range.barsAfter < 100 &&
      previous.barsAfter !== undefined &&
      range.barsAfter < previous.barsAfter;
    if (!older && !newer) return;
    const { signal } = this.controller;
    const key = this.key;
    if (this.firstTimestamp === null || this.lastTimestamp === null) return;
    this.setBusy(true);
    try {
      const candles = older
        ? await this.adapter.fetchBefore(key, this.firstTimestamp, 500, signal)
        : await this.adapter.fetchAfter(
            key,
            this.lastTimestamp + timeframeToMinutes(key.timeframe) * 60_000,
            signal,
          );
      signal.throwIfAborted();
      this.adapter.install(candles, null);
      if (candles.length) {
        this.firstTimestamp = Math.min(
          this.firstTimestamp,
          candles[0].timestamp_ms,
        );
        this.lastTimestamp = Math.max(
          this.lastTimestamp,
          candles.at(-1)!.timestamp_ms,
        );
        await this.adapter.extendIndicators(key, candles, signal);
        signal.throwIfAborted();
      }
      if (older) this.olderExhausted = candles.length < 500;
      else if (candles.length < 500) this.reachedPresent();
    } catch (error) {
      if (!signal.aborted)
        console.error('Failed to page trade history:', error);
    } finally {
      if (!signal.aborted) this.setBusy(false);
    }
  }

  private reachedPresent() {
    this.historical = false;
    this.adapter.historical(false);
    this.onPresent?.(this.lastTimestamp);
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
    history.onPresent = (timestamp) => {
      const key = getKey();
      if (!key) return;
      recovery.start(key);
      recovery.historyLoaded(timestamp);
    };
  return recovery;
}
