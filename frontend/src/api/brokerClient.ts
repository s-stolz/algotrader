import {
  isBrokerConnection,
  isBrokerInstrument,
  isBrokerSymbol,
  type BrokerConnection,
  type BrokerInstrument,
  type BrokerSymbol,
} from '@/types/brokerContracts';
import { parseJsonResponse, withQuery } from './http';

const BASE_URL = '/api/broker';

export async function fetchBrokerConnection(): Promise<BrokerConnection> {
  const value = await parseJsonResponse(
    await fetch(`${BASE_URL}/connection`),
    'Unable to connect to the configured broker account',
  );
  if (!isBrokerConnection(value))
    throw new Error('Invalid broker connection response');
  return value;
}

export async function fetchBrokerSymbols(
  accountId: string,
): Promise<BrokerSymbol[]> {
  const value = await parseJsonResponse(
    await fetch(`${BASE_URL}/symbols/`, {
      headers: { 'X-Account-Id': accountId },
    }),
    'Unable to load broker instruments',
  );
  if (!Array.isArray(value) || !value.every(isBrokerSymbol)) {
    throw new Error('Invalid broker instruments response');
  }
  return value.filter((symbol) => symbol.enabled !== false);
}

export async function fetchBrokerInstrument(
  symbolId: number,
  accountId: string,
): Promise<BrokerInstrument> {
  const value = await parseJsonResponse(
    await fetch(
      withQuery(`${BASE_URL}/setup/instruments/${symbolId}`, {
        account_id: accountId,
      }),
    ),
    'Unable to verify broker instrument',
  );
  if (!isBrokerInstrument(value))
    throw new Error('Invalid broker instrument response');
  if (
    value.broker_symbol_id !== symbolId ||
    value.broker_account_id !== accountId
  ) {
    throw new Error('Broker instrument does not match the selected account');
  }
  return value;
}
