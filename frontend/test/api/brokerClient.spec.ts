import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  fetchBrokerConnection,
  fetchBrokerInstrument,
  fetchBrokerSymbols,
} from '@/api/brokerClient';

const instrument = {
  source_type: 'broker',
  broker_provider: 'ctrader',
  broker_account_id: '42',
  broker_environment: 'demo',
  broker_symbol_id: 9,
  symbol: 'EURUSD',
  exchange: 'BROKER',
  timezone: 'UTC',
  market_type: 'Forex',
  settlement_currency: 'USD',
  minimum_quantity: 1000,
  quantity_step: 1000,
  min_move: null,
  suggested_min_move: 0.00001,
  contract_multiplier: null,
};
const respond = (value: unknown) =>
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(value), { status: 200 })),
  );
afterEach(() => vi.unstubAllGlobals());

describe('broker catalogue client', () => {
  it('reads the configured account and sends its identity to catalogue discovery', async () => {
    const connection = {
      provider: 'ctrader',
      account_id: '42',
      environment: 'demo',
      broker_name: 'BROKER',
    };
    respond(connection);
    expect(await fetchBrokerConnection()).toEqual(connection);
    respond([
      { symbolId: 9, symbolName: 'EURUSD', enabled: true },
      { symbolId: 10, symbolName: 'DISABLED', enabled: false },
    ]);
    expect(await fetchBrokerSymbols('42')).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith('/api/broker/symbols/', {
      headers: { 'X-Account-Id': '42' },
    });
  });
  it('keeps uncertain specifications unresolved and rejects mismatched accounts', async () => {
    respond(instrument);
    expect(await fetchBrokerInstrument(9, '42')).toMatchObject({
      min_move: null,
      contract_multiplier: null,
    });
    respond(instrument);
    await expect(fetchBrokerInstrument(9, '43')).rejects.toThrow(
      'does not match',
    );
  });
});
