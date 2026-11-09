-- Supply verified specifications with SET algotrader.market_specs = '<JSON array>'
-- on the migration connection. No production instrument values are inferred.
ALTER TABLE markets ADD COLUMN settlement_currency VARCHAR(12);
ALTER TABLE markets ADD COLUMN contract_multiplier DOUBLE PRECISION;
ALTER TABLE markets ADD COLUMN minimum_quantity DOUBLE PRECISION;
ALTER TABLE markets ADD COLUMN quantity_step DOUBLE PRECISION;

UPDATE markets AS market
SET settlement_currency = spec.settlement_currency,
    contract_multiplier = spec.contract_multiplier,
    minimum_quantity = spec.minimum_quantity,
    quantity_step = spec.quantity_step
FROM jsonb_to_recordset(
    COALESCE(NULLIF(current_setting('algotrader.market_specs', true), ''), '[]')::jsonb
) AS spec(symbol_id INTEGER, settlement_currency TEXT, contract_multiplier DOUBLE PRECISION,
          minimum_quantity DOUBLE PRECISION, quantity_step DOUBLE PRECISION)
WHERE market.symbol_id = spec.symbol_id;

-- IC Trading symbol response verified 2026-11-09. Quantities use asset units,
-- not lots. cTrader minVolume/stepVolume are hundredths of a unit.
-- https://help.ctrader.com/open-api/model-messages/#protooasymbol
UPDATE markets SET settlement_currency = right(symbol, 3), contract_multiplier = 1,
    minimum_quantity = CASE WHEN symbol = 'BTCUSD' THEN 0.01 ELSE 1000 END,
    quantity_step = CASE WHEN symbol = 'BTCUSD' THEN 0.01 ELSE 1000 END
WHERE upper(exchange) = 'IC TRADING'
  AND symbol IN ('EURUSD','GBPUSD','AUDUSD','NZDUSD','USDJPY','USDCHF','USDCAD','BTCUSD')
  AND settlement_currency IS NULL;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM markets WHERE settlement_currency IS NULL
        OR contract_multiplier IS NULL OR minimum_quantity IS NULL OR quantity_step IS NULL) THEN
        RAISE EXCEPTION 'Verified instrument specification backfill is required for every existing market';
    END IF;
END $$;

ALTER TABLE markets ALTER COLUMN settlement_currency SET NOT NULL;
ALTER TABLE markets ALTER COLUMN contract_multiplier SET NOT NULL;
ALTER TABLE markets ALTER COLUMN minimum_quantity SET NOT NULL;
ALTER TABLE markets ALTER COLUMN quantity_step SET NOT NULL;
ALTER TABLE markets ADD CONSTRAINT markets_symbol_exchange_key UNIQUE (symbol, exchange);
ALTER TABLE markets ADD CONSTRAINT markets_positive_specification CHECK (
    min_move > 0 AND min_move < 'Infinity'::float8
    AND contract_multiplier > 0 AND contract_multiplier < 'Infinity'::float8
    AND minimum_quantity > 0 AND minimum_quantity < 'Infinity'::float8
    AND quantity_step > 0 AND quantity_step < 'Infinity'::float8
    AND length(trim(settlement_currency)) > 0
);

-- Preserve old name-based replay reads without rewriting immutable requests.
CREATE TABLE market_aliases (
    symbol VARCHAR(10) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    symbol_id INTEGER NOT NULL REFERENCES markets(symbol_id) ON DELETE CASCADE,
    PRIMARY KEY (symbol, exchange)
);
INSERT INTO market_aliases SELECT symbol, exchange, symbol_id FROM markets;

ALTER TABLE backtest_fills DROP CONSTRAINT backtest_fills_exit_reason_check;
ALTER TABLE backtest_fills ADD CONSTRAINT backtest_fills_exit_reason_check
    CHECK (exit_reason IS NULL OR exit_reason IN ('signal','stop_loss','take_profit','account_depleted'));
ALTER TABLE backtest_closed_trades DROP CONSTRAINT backtest_closed_trades_exit_reason_check;
ALTER TABLE backtest_closed_trades ADD CONSTRAINT backtest_closed_trades_exit_reason_check
    CHECK (exit_reason IN ('signal','stop_loss','take_profit','account_depleted'));

CREATE UNIQUE INDEX markets_normalized_identity_key
    ON markets (upper(trim(symbol)), upper(trim(exchange)));
CREATE UNIQUE INDEX market_aliases_normalized_identity_key
    ON market_aliases (upper(trim(symbol)), upper(trim(exchange)));
