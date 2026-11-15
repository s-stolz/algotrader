import type {
  ChartSessionKey,
  ChartSessionOlderHistorySignal,
  ChartSessionSubscriptionsAdapter,
} from './chartSession';

export class ChartOlderHistory {
  private revision = 0;
  private rangeVersion = 0;
  private range: ChartSessionOlderHistorySignal | null = null;
  private loading = false;
  private exhausted = false;

  constructor(private readonly adapter: ChartSessionSubscriptionsAdapter) {}

  cancel(): void {
    this.revision += 1;
    this.range = null;
    this.loading = false;
    this.exhausted = false;
  }

  request(key: ChartSessionKey, range: ChartSessionOlderHistorySignal): void {
    this.range = { ...range };
    this.rangeVersion += 1;
    if (!this.loading && this.needsHistory())
      void this.load({ ...key }, this.revision);
  }

  private needsHistory(): boolean {
    return (
      !this.exhausted &&
      !!this.range &&
      !this.range.scrollToRealtime &&
      this.range.barsBefore < 100
    );
  }

  private async load(key: ChartSessionKey, revision: number): Promise<void> {
    this.loading = true;
    const isCurrent = () => revision === this.revision;
    try {
      while (isCurrent() && this.needsHistory()) {
        const endMs = this.adapter.getOldestCandleTimestampMs();
        if (endMs === null) return;
        const candles = await this.adapter.fetchOlderCandles(key, endMs);
        if (!isCurrent()) return;
        const rangeVersion = this.rangeVersion;
        await this.adapter.prependOlderCandles(key, candles);
        if (!isCurrent()) return;
        await this.adapter.renderOlderCandles(key);
        if (!isCurrent()) return;
        // A render callback may already have reported the expanded coverage.
        if (rangeVersion === this.rangeVersion && this.range)
          this.range.barsBefore += candles.length;
        this.exhausted =
          !candles.length ||
          (this.adapter.getOldestCandleTimestampMs() ?? endMs) >= endMs;
        try {
          await this.adapter.requestOlderIndicators(key);
        } catch (error) {
          if (isCurrent())
            this.adapter.reportOlderIndicatorFetchError?.(key, error);
          return;
        }
        if (!isCurrent()) return;
        this.range = this.adapter.getHistoryRange?.() ?? this.range;
      }
    } catch (error) {
      if (isCurrent()) this.adapter.reportOlderCandleFetchError?.(key, error);
    } finally {
      if (isCurrent()) this.loading = false;
    }
  }
}
