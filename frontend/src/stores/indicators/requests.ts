import type { IndicatorQuery } from '@/types/contracts';
import type { WebSocketSendPayload } from '@/utils/websocketService';
import type { IndicatorLiveSubscription, IndicatorStoreQuery } from './types';

export function toClientQuery(
  query: IndicatorStoreQuery,
): IndicatorQuery | null {
  if (!query.symbol || !query.timeframe) {
    return null;
  }

  const clientQuery: IndicatorQuery = {
    symbol: query.symbol,
    timeframe: query.timeframe,
  };

  if (query.exchange !== undefined) {
    clientQuery.exchange = query.exchange;
  }
  if (query.startMs !== undefined || query.start_ms !== undefined) {
    clientQuery.startMs = query.startMs ?? query.start_ms ?? null;
  }
  if (query.endMs !== undefined || query.end_ms !== undefined) {
    clientQuery.endMs = query.endMs ?? query.end_ms ?? null;
  }
  if (query.limit !== undefined) {
    clientQuery.limit = query.limit;
  }

  return clientQuery;
}

export function toSubscriptionPayload(
  subscription: IndicatorLiveSubscription,
): WebSocketSendPayload {
  return {
    symbol: subscription.symbol,
    timeframe: subscription.timeframe,
    exchange: subscription.exchange,
    indicatorId: subscription.indicatorId,
    parameters: subscription.parameters,
    clientIndicatorId: subscription.clientIndicatorId,
  };
}
