-- Backtest history is deliberately discarded for the unified model. Stop API
-- and workers before applying; an unverified execution slot cannot be cleared.
LOCK TABLE backtest_execution_slot IN ACCESS EXCLUSIVE MODE;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM backtest_execution_slot
        WHERE owner_token IS NOT NULL OR run_id IS NOT NULL OR fault_code IS NOT NULL) THEN
        RAISE EXCEPTION 'Stop and settle backtest execution before applying V020';
    END IF;
END $$;
TRUNCATE backtest_execution_slot, backtest_queue_turns, backtest_worker_heartbeats,
    backtest_batch_commands, backtest_batch_events, backtest_fills,
    backtest_closed_trades, backtest_runs, backtest_batches;
INSERT INTO backtest_execution_slot (slot_id) VALUES (1);

ALTER TABLE backtest_batches RENAME TO backtests;
ALTER TABLE backtests RENAME COLUMN batch_id TO backtest_id;
ALTER TABLE backtest_batch_events RENAME TO backtest_events;
ALTER TABLE backtest_events RENAME COLUMN batch_id TO backtest_id;
ALTER TABLE backtest_batch_commands RENAME TO backtest_commands;
ALTER TABLE backtest_commands RENAME COLUMN batch_id TO backtest_id;
ALTER TABLE backtest_runs RENAME COLUMN batch_id TO backtest_id;
ALTER TABLE backtest_runs RENAME COLUMN member_ordinal TO run_ordinal;
ALTER TABLE backtest_runs DROP COLUMN name;
ALTER TABLE backtest_runs ALTER COLUMN backtest_id SET NOT NULL;
ALTER TABLE backtest_runs ALTER COLUMN run_ordinal SET NOT NULL;
ALTER TABLE backtest_runs DROP CONSTRAINT backtest_member_identity_check;
ALTER TABLE backtest_runs ADD CONSTRAINT backtest_run_identity_check CHECK (
    run_ordinal >= 0 AND request_schema_version = 3
    AND jsonb_array_length(request->'symbols') = 1
    AND request->'strategy'->>'strategy_version' IS NOT NULL
);
ALTER TABLE backtest_queue_turns DROP CONSTRAINT backtest_queue_turn_identity_check;
ALTER TABLE backtest_queue_turns DROP COLUMN run_id;
ALTER TABLE backtest_queue_turns RENAME COLUMN batch_id TO backtest_id;
ALTER TABLE backtest_queue_turns ALTER COLUMN backtest_id SET NOT NULL;

CREATE OR REPLACE FUNCTION guard_backtest_membership() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' AND EXISTS (
        SELECT 1 FROM backtest_events
        WHERE backtest_id = NEW.backtest_id AND event_type = 'accepted'
    ) THEN
        RAISE EXCEPTION 'Accepted Backtest membership is immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND (OLD.backtest_id IS DISTINCT FROM NEW.backtest_id
        OR OLD.run_ordinal IS DISTINCT FROM NEW.run_ordinal
        OR OLD.request IS DISTINCT FROM NEW.request) THEN
        RAISE EXCEPTION 'Backtest membership and request are immutable';
    END IF;
    IF TG_OP = 'DELETE' AND EXISTS (
        SELECT 1 FROM backtests WHERE backtest_id = OLD.backtest_id
    ) THEN
        RAISE EXCEPTION 'Runs cannot be deleted individually';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
