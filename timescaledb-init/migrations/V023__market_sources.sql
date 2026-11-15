ALTER TABLE markets
    ALTER COLUMN symbol TYPE VARCHAR(128),
    ALTER COLUMN exchange TYPE VARCHAR(128),
    ADD COLUMN source_type VARCHAR(8) NOT NULL DEFAULT 'custom',
    ADD COLUMN broker_provider VARCHAR(16),
    ADD COLUMN broker_account_id VARCHAR(128),
    ADD COLUMN broker_environment VARCHAR(4),
    ADD COLUMN broker_symbol_id BIGINT,
    ADD COLUMN live_start_ms BIGINT,
    ADD CONSTRAINT markets_source_check CHECK (
        (source_type = 'custom' AND broker_provider IS NULL AND broker_account_id IS NULL
         AND broker_environment IS NULL AND broker_symbol_id IS NULL AND live_start_ms IS NULL)
        OR
        (source_type = 'broker' AND broker_provider IS NOT NULL AND broker_provider = 'ctrader'
         AND broker_account_id IS NOT NULL AND length(broker_account_id) > 0
         AND broker_environment IS NOT NULL AND broker_environment IN ('demo', 'live')
         AND broker_symbol_id IS NOT NULL AND broker_symbol_id > 0
         AND live_start_ms IS NOT NULL AND live_start_ms >= 0 AND live_start_ms % 60000 = 0)
    );

CREATE FUNCTION preserve_market_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(OLD.source_type, OLD.broker_provider, OLD.broker_account_id,
           OLD.broker_environment, OLD.broker_symbol_id, OLD.live_start_ms)
       IS DISTINCT FROM
       ROW(NEW.source_type, NEW.broker_provider, NEW.broker_account_id,
           NEW.broker_environment, NEW.broker_symbol_id, NEW.live_start_ms)
       OR (OLD.source_type = 'broker' AND
           ROW(OLD.symbol, OLD.exchange) IS DISTINCT FROM ROW(NEW.symbol, NEW.exchange)) THEN
        RAISE EXCEPTION 'Market source cannot change after creation' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER markets_preserve_source BEFORE UPDATE ON markets
FOR EACH ROW EXECUTE FUNCTION preserve_market_source();
