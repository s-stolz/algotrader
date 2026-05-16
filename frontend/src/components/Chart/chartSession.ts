import type { CandleUpdateMessage, ChartCandle } from '@/types/contracts';

export interface ChartSessionKeyInput {
  symbol?: string | null;
  exchange?: string | null;
  timeframe?: string | null;
}

export interface ChartSessionKey {
  symbol: string;
  exchange: string | null;
  timeframe: string;
}

export type ChartSessionCandleHandler = (message: CandleUpdateMessage) => void;
export type ChartSessionLiveCandleReceiver = (
  message: CandleUpdateMessage,
  key: ChartSessionKey,
) => void;

export type ChartSessionSubscriptionOperation = 'subscribe' | 'unsubscribe';

const LIVE_TAIL_BUFFER_CAP = 3;

export interface ChartSessionSubscriptionsAdapter {
  subscribeCandles(key: ChartSessionKey): Promise<void> | void;
  unsubscribeCandles(key: ChartSessionKey): Promise<void> | void;
  onCandleUpdate(handler: ChartSessionCandleHandler): void;
  offCandleUpdate(handler: ChartSessionCandleHandler): void;
  fetchCandles(key: ChartSessionKey): Promise<readonly ChartCandle[]> | readonly ChartCandle[];
  renderCandles(key: ChartSessionKey, candles: readonly ChartCandle[]): Promise<void> | void;
  requestIndicators(key: ChartSessionKey): Promise<void> | void;
  unsubscribeIndicators(): Promise<void> | void;
  resetIndicatorHistory?(): void;
  reportCandleFetchError?: (key: ChartSessionKey, error: unknown) => void;
  reportLiveTailBufferOverflow?: (key: ChartSessionKey, candle: CandleUpdateMessage) => void;
  reportSubscriptionError?: (
    operation: ChartSessionSubscriptionOperation,
    key: ChartSessionKey,
    error: unknown,
  ) => void;
}

interface InFlightCandleFetch {
  key: ChartSessionKey;
  revision: number;
  indicatorCleanup: Promise<void>;
  liveTail: CandleUpdateMessage[];
}

function normalizeSessionKey(input: ChartSessionKeyInput | null | undefined): ChartSessionKey | null {
  if (!input?.symbol || !input.timeframe) {
    return null;
  }

  return {
    symbol: input.symbol,
    exchange: input.exchange ?? null,
    timeframe: input.timeframe,
  };
}

function cloneSessionKey(key: ChartSessionKey): ChartSessionKey {
  return {
    symbol: key.symbol,
    exchange: key.exchange,
    timeframe: key.timeframe,
  };
}

function sessionKeysEqual(left: ChartSessionKey | null, right: ChartSessionKey | null): boolean {
  if (left === right) return true;
  if (!left || !right) return false;

  return (
    left.symbol === right.symbol &&
    left.exchange === right.exchange &&
    left.timeframe === right.timeframe
  );
}

function candleMatchesSession(message: CandleUpdateMessage, key: ChartSessionKey): boolean {
  return message.symbol === key.symbol && message.timeframe === key.timeframe;
}

export class ChartSession {
  private activeKey: ChartSessionKey | null = null;
  private listener: ChartSessionCandleHandler | null = null;
  private liveCandleReceiver: ChartSessionLiveCandleReceiver | null = null;
  private inFlightCandleFetch: InFlightCandleFetch | null = null;
  private revision = 0;

  constructor(private readonly adapter: ChartSessionSubscriptionsAdapter) {}

  getActiveKey(): ChartSessionKey | null {
    return this.activeKey ? cloneSessionKey(this.activeKey) : null;
  }

  async setSession(
    input: ChartSessionKeyInput | null | undefined,
    receiveLiveCandle: ChartSessionLiveCandleReceiver,
  ): Promise<void> {
    const nextKey = normalizeSessionKey(input);

    if (sessionKeysEqual(this.activeKey, nextKey)) {
      this.liveCandleReceiver = receiveLiveCandle;
      return;
    }

    const revision = this.revision + 1;
    this.revision = revision;
    const previousKey = this.activeKey;
    const previousListener = this.listener;

    this.activeKey = null;
    this.listener = null;
    this.liveCandleReceiver = null;
    this.inFlightCandleFetch = null;

    if (previousListener) {
      this.adapter.offCandleUpdate(previousListener);
    }

    if (previousKey) {
      await this.unsubscribe(previousKey);
    }

    const indicatorCleanup = previousKey || nextKey
      ? this.startIndicatorCleanup()
      : Promise.resolve();

    if (revision !== this.revision || !nextKey) {
      await indicatorCleanup;
      return;
    }

    this.adapter.resetIndicatorHistory?.();
    this.activeKey = cloneSessionKey(nextKey);
    this.liveCandleReceiver = receiveLiveCandle;
    this.listener = (message) => {
      this.handleCandleUpdate(message);
    };
    this.adapter.onCandleUpdate(this.listener);

    await this.subscribe(nextKey);

    if (revision !== this.revision) {
      await indicatorCleanup;
      if (!sessionKeysEqual(this.activeKey, nextKey)) {
        await this.unsubscribe(nextKey);
      }
      return;
    }

    if (!sessionKeysEqual(this.activeKey, nextKey)) {
      await indicatorCleanup;
      await this.unsubscribe(nextKey);
      return;
    }

    await this.fetchCandlesForSession(nextKey, revision, indicatorCleanup);
  }

  async stop(): Promise<void> {
    this.revision += 1;
    const previousKey = this.activeKey;
    const previousListener = this.listener;

    this.activeKey = null;
    this.listener = null;
    this.liveCandleReceiver = null;
    this.inFlightCandleFetch = null;

    if (previousListener) {
      this.adapter.offCandleUpdate(previousListener);
    }

    if (previousKey) {
      await this.unsubscribe(previousKey);
    }

    await this.unsubscribeIndicators();
  }

  private handleCandleUpdate(message: CandleUpdateMessage): void {
    if (!this.activeKey || !this.liveCandleReceiver) return;
    if (!candleMatchesSession(message, this.activeKey)) return;

    if (this.bufferLiveCandleIfFetchInFlight(message, this.activeKey)) {
      return;
    }

    this.liveCandleReceiver(message, cloneSessionKey(this.activeKey));
  }

  private bufferLiveCandleIfFetchInFlight(
    message: CandleUpdateMessage,
    key: ChartSessionKey,
  ): boolean {
    const inFlight = this.inFlightCandleFetch;
    if (!inFlight || !this.isCurrentFetch(inFlight)) {
      return false;
    }
    if (!sessionKeysEqual(inFlight.key, key)) {
      return false;
    }

    const last = inFlight.liveTail[inFlight.liveTail.length - 1];
    const liveCandle = { ...message };
    if (!last) {
      inFlight.liveTail.push(liveCandle);
      return true;
    }

    if (liveCandle.timestamp_ms < last.timestamp_ms) {
      return true;
    }

    if (liveCandle.timestamp_ms === last.timestamp_ms) {
      inFlight.liveTail[inFlight.liveTail.length - 1] = liveCandle;
      return true;
    }

    if (inFlight.liveTail.length < LIVE_TAIL_BUFFER_CAP) {
      inFlight.liveTail.push(liveCandle);
    } else {
      this.handleLiveTailBufferOverflow(inFlight, liveCandle);
    }
    return true;
  }

  private handleLiveTailBufferOverflow(
    inFlight: InFlightCandleFetch,
    candle: CandleUpdateMessage,
  ): void {
    if (!this.isCurrentFetch(inFlight)) return;

    const sessionKey = cloneSessionKey(inFlight.key);
    this.adapter.reportLiveTailBufferOverflow?.(sessionKey, { ...candle });
    void this.fetchCandlesForSession(
      sessionKey,
      inFlight.revision,
      inFlight.indicatorCleanup,
    );
  }

  private async subscribe(key: ChartSessionKey): Promise<void> {
    try {
      await this.adapter.subscribeCandles(cloneSessionKey(key));
    } catch (error) {
      this.adapter.reportSubscriptionError?.('subscribe', cloneSessionKey(key), error);
    }
  }

  private async unsubscribe(key: ChartSessionKey): Promise<void> {
    try {
      await this.adapter.unsubscribeCandles(cloneSessionKey(key));
    } catch (error) {
      this.adapter.reportSubscriptionError?.('unsubscribe', cloneSessionKey(key), error);
    }
  }

  private async unsubscribeIndicators(): Promise<void> {
    await this.adapter.unsubscribeIndicators();
  }

  private startIndicatorCleanup(): Promise<void> {
    const cleanup = this.unsubscribeIndicators();
    cleanup.catch(() => undefined);
    return cleanup;
  }

  private async fetchCandlesForSession(
    key: ChartSessionKey,
    revision: number,
    indicatorCleanup: Promise<void>,
  ): Promise<void> {
    const sessionKey = cloneSessionKey(key);
    const inFlight: InFlightCandleFetch = {
      key: sessionKey,
      revision,
      indicatorCleanup,
      liveTail: [],
    };
    this.inFlightCandleFetch = inFlight;
    let candles: readonly ChartCandle[];

    try {
      candles = await this.adapter.fetchCandles(sessionKey);
    } catch (error) {
      const shouldReport = this.isCurrentFetch(inFlight);
      if (this.inFlightCandleFetch === inFlight) {
        this.inFlightCandleFetch = null;
      }
      if (shouldReport) {
        this.adapter.reportCandleFetchError?.(cloneSessionKey(sessionKey), error);
      }
      return;
    }

    if (!this.isCurrentFetch(inFlight)) {
      if (this.inFlightCandleFetch === inFlight) {
        this.inFlightCandleFetch = null;
      }
      return;
    }

    await this.adapter.renderCandles(cloneSessionKey(sessionKey), candles);

    if (!this.isCurrentFetch(inFlight)) {
      if (this.inFlightCandleFetch === inFlight) {
        this.inFlightCandleFetch = null;
      }
      return;
    }

    if (this.inFlightCandleFetch === inFlight) {
      this.inFlightCandleFetch = null;
    }
    for (const liveCandle of inFlight.liveTail) {
      this.liveCandleReceiver?.(liveCandle, cloneSessionKey(sessionKey));
    }

    await indicatorCleanup;

    if (!this.isCurrentSession(sessionKey, revision)) {
      return;
    }

    await this.adapter.requestIndicators(cloneSessionKey(sessionKey));
  }

  private isCurrentSession(key: ChartSessionKey, revision: number): boolean {
    return revision === this.revision && sessionKeysEqual(this.activeKey, key);
  }

  private isCurrentFetch(inFlight: InFlightCandleFetch): boolean {
    return (
      this.inFlightCandleFetch === inFlight &&
      this.isCurrentSession(inFlight.key, inFlight.revision)
    );
  }
}

export function createChartSession(adapter: ChartSessionSubscriptionsAdapter): ChartSession {
  return new ChartSession(adapter);
}
