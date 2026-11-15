CREATE TABLE history_download_jobs (
    id VARCHAR(36) PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL UNIQUE,
    market_id INTEGER NOT NULL REFERENCES markets(symbol_id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL,
    start_ms BIGINT,
    candle_count INTEGER,
    end_exclusive_ms BIGINT NOT NULL,
    cursor_ms BIGINT NOT NULL,
    fetched_count BIGINT NOT NULL DEFAULT 0,
    inserted_count BIGINT NOT NULL DEFAULT 0,
    source_snapshot JSONB NOT NULL,
    owner_token VARCHAR(128),
    revision BIGINT NOT NULL,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    failure_reason TEXT,
    availability_reason TEXT,
    first_inserted_ms BIGINT,
    last_inserted_ms BIGINT,
    CONSTRAINT history_download_jobs_status_check CHECK (
        status IN ('queued', 'downloading', 'completed', 'failed', 'cancelled')
    ),
    CONSTRAINT history_download_jobs_selector_check CHECK (
        (start_ms IS NOT NULL AND start_ms >= 0 AND start_ms % 60000 = 0
         AND candle_count IS NULL AND cursor_ms >= start_ms)
        OR (start_ms IS NULL AND candle_count IS NOT NULL AND candle_count > 0)
    ),
    CONSTRAINT history_download_jobs_progress_check CHECK (
        cursor_ms >= 0 AND cursor_ms <= end_exclusive_ms AND cursor_ms % 60000 = 0
        AND end_exclusive_ms % 60000 = 0 AND fetched_count >= inserted_count
        AND inserted_count >= 0 AND revision > 0
    ),
    CONSTRAINT history_download_jobs_owner_check CHECK (
        (status = 'downloading' AND owner_token IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR (status <> 'downloading' AND owner_token IS NULL AND lease_expires_at IS NULL)
    )
);
CREATE UNIQUE INDEX history_download_jobs_one_active_market ON history_download_jobs(market_id)
WHERE status IN ('queued', 'downloading');
CREATE INDEX history_download_jobs_created ON history_download_jobs(created_at, id);

CREATE FUNCTION guard_market_download_deletion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM history_download_jobs
               WHERE market_id = OLD.symbol_id AND status IN ('queued', 'downloading')) THEN
        RAISE EXCEPTION 'Cancel the active historical download before deleting its market'
            USING ERRCODE = '23514';
    END IF;
    RETURN OLD;
END;
$$;
CREATE TRIGGER markets_guard_download_deletion BEFORE DELETE ON markets
FOR EACH ROW EXECUTE FUNCTION guard_market_download_deletion();

CREATE FUNCTION preserve_history_download_request() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(OLD.id, OLD.request_id, OLD.market_id, OLD.start_ms, OLD.candle_count,
           OLD.end_exclusive_ms, OLD.source_snapshot, OLD.created_at)
       IS DISTINCT FROM
       ROW(NEW.id, NEW.request_id, NEW.market_id, NEW.start_ms, NEW.candle_count,
           NEW.end_exclusive_ms, NEW.source_snapshot, NEW.created_at) THEN
        RAISE EXCEPTION 'Accepted historical download request is immutable' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER history_download_jobs_preserve_request BEFORE UPDATE ON history_download_jobs
FOR EACH ROW EXECUTE FUNCTION preserve_history_download_request();
