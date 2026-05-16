import type { CandleUpdateMessage } from '@/types/contracts';

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

export interface ChartSessionSubscriptionsAdapter {
  subscribeCandles(key: ChartSessionKey): Promise<void> | void;
  unsubscribeCandles(key: ChartSessionKey): Promise<void> | void;
  onCandleUpdate(handler: ChartSessionCandleHandler): void;
  offCandleUpdate(handler: ChartSessionCandleHandler): void;
  reportSubscriptionError?: (
    operation: ChartSessionSubscriptionOperation,
    key: ChartSessionKey,
    error: unknown,
  ) => void;
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

    if (previousListener) {
      this.adapter.offCandleUpdate(previousListener);
    }

    if (previousKey) {
      await this.unsubscribe(previousKey);
    }

    if (revision !== this.revision || !nextKey) {
      return;
    }

    this.activeKey = cloneSessionKey(nextKey);
    this.liveCandleReceiver = receiveLiveCandle;
    this.listener = (message) => {
      this.handleCandleUpdate(message);
    };
    this.adapter.onCandleUpdate(this.listener);

    await this.subscribe(nextKey);

    if (revision !== this.revision && !sessionKeysEqual(this.activeKey, nextKey)) {
      await this.unsubscribe(nextKey);
    }
  }

  async stop(): Promise<void> {
    this.revision += 1;
    const previousKey = this.activeKey;
    const previousListener = this.listener;

    this.activeKey = null;
    this.listener = null;
    this.liveCandleReceiver = null;

    if (previousListener) {
      this.adapter.offCandleUpdate(previousListener);
    }

    if (previousKey) {
      await this.unsubscribe(previousKey);
    }
  }

  private handleCandleUpdate(message: CandleUpdateMessage): void {
    if (!this.activeKey || !this.liveCandleReceiver) return;
    if (!candleMatchesSession(message, this.activeKey)) return;

    this.liveCandleReceiver(message, cloneSessionKey(this.activeKey));
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
}

export function createChartSession(adapter: ChartSessionSubscriptionsAdapter): ChartSession {
  return new ChartSession(adapter);
}
