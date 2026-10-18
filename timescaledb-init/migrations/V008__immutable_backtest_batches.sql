-- Existing standalone runs retain NULL batch identity and their original requests.
CREATE TABLE backtest_batches (
    batch_id VARCHAR(36) PRIMARY KEY,
    submission_id VARCHAR(36) NOT NULL UNIQUE,
    status VARCHAR(16) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'pausing', 'paused', 'cancelling', 'completed', 'cancelled')),
    accepted_at TIMESTAMPTZ NOT NULL,
    lifecycle_revision INTEGER NOT NULL DEFAULT 0 CHECK (lifecycle_revision >= 0),
    definition_schema_version INTEGER NOT NULL CHECK (definition_schema_version = 1),
    accepted_definition JSONB NOT NULL,
    strategy_metadata JSONB NOT NULL,
    raw_count INTEGER NOT NULL CHECK (raw_count > 0),
    member_count INTEGER NOT NULL CHECK (member_count > 0),
    excluded_count INTEGER NOT NULL CHECK (excluded_count >= 0),
    CHECK (raw_count = member_count + excluded_count)
);

ALTER TABLE backtest_runs
    ADD COLUMN batch_id VARCHAR(36) REFERENCES backtest_batches(batch_id) ON DELETE RESTRICT,
    ADD COLUMN member_ordinal INTEGER,
    ADD CONSTRAINT backtest_member_identity_check
        CHECK ((batch_id IS NULL AND member_ordinal IS NULL)
            OR (batch_id IS NOT NULL AND member_ordinal >= 0
                AND request_schema_version = 3
                AND jsonb_array_length(request->'symbols') = 1
                AND request->'strategy'->>'strategy_version' IS NOT NULL));

CREATE UNIQUE INDEX uq_backtest_batch_ordinal
    ON backtest_runs (batch_id, member_ordinal) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_backtest_batch_members ON backtest_runs (batch_id, member_ordinal);

CREATE TABLE backtest_batch_events (
    batch_id VARCHAR(36) NOT NULL REFERENCES backtest_batches(batch_id) ON DELETE CASCADE,
    revision INTEGER NOT NULL CHECK (revision >= 0),
    event_type VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    reason TEXT,
    PRIMARY KEY (batch_id, revision)
);

-- Only whole-batch deletion may remove members; a later migration can introduce
-- an explicit transaction-scoped deletion command for that operation.
CREATE FUNCTION guard_backtest_membership() RETURNS trigger LANGUAGE plpgsql AS $$
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
    IF TG_OP = 'DELETE' AND OLD.batch_id IS NOT NULL THEN
        RAISE EXCEPTION 'Backtest batch members cannot be deleted individually';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER backtest_membership_guard
    BEFORE INSERT OR UPDATE OR DELETE ON backtest_runs
    FOR EACH ROW EXECUTE FUNCTION guard_backtest_membership();
