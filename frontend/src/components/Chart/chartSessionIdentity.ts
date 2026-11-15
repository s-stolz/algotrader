import type {
  CandleUpdateMessage,
  StoredCurrentMarket,
} from '@/types/contracts';

export interface ChartSessionKeyInput {
  market_id?: number | null;
  source_type?: 'custom' | 'broker';
  symbol?: string | null;
  exchange?: string | null;
  timeframe?: string | null;
}

export interface ChartSessionKey {
  market_id?: number | null;
  source_type?: 'custom' | 'broker';
  symbol: string;
  exchange: string | null;
  timeframe: string;
}

export function normalizeSessionKey(
  input: ChartSessionKeyInput | null | undefined,
): ChartSessionKey | null {
  if (!input?.symbol || !input.timeframe) {
    return null;
  }

  return {
    market_id: input.market_id,
    source_type: input.source_type,
    symbol: input.symbol,
    exchange: input.exchange ?? null,
    timeframe: input.timeframe,
  };
}

export function cloneSessionKey(key: ChartSessionKey): ChartSessionKey {
  return {
    market_id: key.market_id,
    source_type: key.source_type,
    symbol: key.symbol,
    exchange: key.exchange,
    timeframe: key.timeframe,
  };
}

export function sessionKeysEqual(
  left: ChartSessionKey | null,
  right: ChartSessionKey | null,
): boolean {
  if (left === right) return true;
  if (!left || !right) return false;

  return (
    left.market_id === right.market_id &&
    left.source_type === right.source_type &&
    left.symbol === right.symbol &&
    left.exchange === right.exchange &&
    left.timeframe === right.timeframe
  );
}

export function candleMatchesSession(
  message: CandleUpdateMessage,
  key: ChartSessionKey,
): boolean {
  return (
    key.source_type !== 'custom' &&
    (key.market_id === undefined || key.market_id === message.market_id) &&
    message.symbol === key.symbol &&
    message.timeframe === key.timeframe
  );
}

export function createMarketSessionKey(
  market: StoredCurrentMarket,
  timeframe: string | null,
): ChartSessionKeyInput {
  return {
    market_id: market.symbol_id,
    source_type: market.source_type ?? 'custom',
    symbol: market.symbol,
    exchange: market.exchange,
    timeframe,
  };
}

export function chartSessionIdentity(key: ChartSessionKeyInput): string {
  return JSON.stringify([
    key.market_id,
    key.source_type,
    key.symbol,
    key.exchange ?? null,
    key.timeframe,
  ]);
}
