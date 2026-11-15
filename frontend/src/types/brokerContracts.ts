import { isRecord, isFiniteNumber, isNonEmptyString } from './transportValues';

export interface BrokerConnection {
  provider: 'ctrader';
  account_id: string;
  environment: 'demo' | 'live';
  broker_name: string;
}

export interface BrokerSymbol {
  symbolId: number;
  symbolName: string;
  enabled: boolean | null;
}

export interface BrokerInstrument {
  source_type: 'broker';
  broker_provider: 'ctrader';
  broker_account_id: string;
  broker_environment: 'demo' | 'live';
  broker_symbol_id: number;
  symbol: string;
  exchange: string;
  timezone: string | null;
  market_type: string | null;
  settlement_currency: string | null;
  minimum_quantity: number | null;
  quantity_step: number | null;
  min_move: null;
  suggested_min_move: number | null;
  contract_multiplier: null;
}

export function isBrokerConnection(value: unknown): value is BrokerConnection {
  return (
    isRecord(value) &&
    value.provider === 'ctrader' &&
    isNonEmptyString(value.account_id) &&
    isNonEmptyString(value.broker_name) &&
    (value.environment === 'demo' || value.environment === 'live')
  );
}

export function isBrokerSymbol(value: unknown): value is BrokerSymbol {
  return (
    isRecord(value) &&
    Number.isInteger(value.symbolId) &&
    Number(value.symbolId) > 0 &&
    isNonEmptyString(value.symbolName) &&
    (value.enabled === null || typeof value.enabled === 'boolean')
  );
}

export function isBrokerInstrument(value: unknown): value is BrokerInstrument {
  if (!isRecord(value)) return false;
  return (
    value.source_type === 'broker' &&
    value.broker_provider === 'ctrader' &&
    isNonEmptyString(value.broker_account_id) &&
    (value.broker_environment === 'demo' ||
      value.broker_environment === 'live') &&
    Number.isInteger(value.broker_symbol_id) &&
    Number(value.broker_symbol_id) > 0 &&
    isNonEmptyString(value.symbol) &&
    isNonEmptyString(value.exchange) &&
    ['timezone', 'market_type', 'settlement_currency'].every(
      (key) => value[key] === null || isNonEmptyString(value[key]),
    ) &&
    ['minimum_quantity', 'quantity_step', 'suggested_min_move'].every(
      (key) =>
        value[key] === null || (isFiniteNumber(value[key]) && value[key] > 0),
    ) &&
    value.min_move === null &&
    value.contract_multiplier === null
  );
}
