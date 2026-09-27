-- Child removal is possible only as a consequence of deleting its parent.
ALTER TABLE backtest_runs DROP CONSTRAINT backtest_runs_batch_id_fkey;
ALTER TABLE backtest_runs ADD CONSTRAINT backtest_runs_batch_id_fkey
    FOREIGN KEY (batch_id) REFERENCES backtest_batches(batch_id) ON DELETE CASCADE;

CREATE OR REPLACE FUNCTION guard_backtest_membership() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.batch_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM backtest_batch_events
        WHERE batch_id = NEW.batch_id AND event_type = 'accepted'
    ) THEN
        RAISE EXCEPTION 'Accepted Backtest Batch membership is immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND (OLD.batch_id IS DISTINCT FROM NEW.batch_id
        OR OLD.member_ordinal IS DISTINCT FROM NEW.member_ordinal
        OR OLD.request IS DISTINCT FROM NEW.request) THEN
        RAISE EXCEPTION 'Backtest membership and request are immutable';
    END IF;
    IF TG_OP = 'DELETE' AND OLD.batch_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM backtest_batches WHERE batch_id = OLD.batch_id
    ) THEN
        RAISE EXCEPTION 'Backtest batch members cannot be deleted individually';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
