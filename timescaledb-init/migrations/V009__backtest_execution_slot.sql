-- A held slot is never expired automatically: only verified child exit and a
-- committed terminal transition may release it. Recovery requires operator
-- confirmation that the previous worker and its descendants have stopped.
CREATE TABLE backtest_execution_slot (
    slot_id INTEGER PRIMARY KEY CHECK (slot_id = 1),
    owner_token VARCHAR(36),
    run_id VARCHAR(36) REFERENCES backtest_runs (run_id),
    fault_code VARCHAR(64),
    fault_message TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT backtest_execution_slot_owner_pair_check
        CHECK ((owner_token IS NULL) = (run_id IS NULL))
);

INSERT INTO backtest_execution_slot (slot_id) VALUES (1);

-- Legacy workers must be stopped before this migration. This guard also keeps
-- their old status-update endpoint from bypassing the global slot afterward.
CREATE FUNCTION require_backtest_execution_slot() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'queued' AND NEW.status = 'running' AND NOT EXISTS (
        SELECT 1 FROM backtest_execution_slot
        WHERE slot_id = 1 AND run_id = NEW.run_id AND owner_token IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'backtest execution slot is required for claim';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER backtest_execution_slot_claim_guard
BEFORE UPDATE OF status ON backtest_runs
FOR EACH ROW EXECUTE FUNCTION require_backtest_execution_slot();
