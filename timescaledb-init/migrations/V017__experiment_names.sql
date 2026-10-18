-- Names belong to experiments, outside immutable execution snapshots. This
-- transaction is the one-time exception that removes legacy naming metadata.
ALTER TABLE backtest_runs ADD COLUMN name VARCHAR(120);
ALTER TABLE backtest_batches ADD COLUMN name VARCHAR(120);

CREATE FUNCTION pg_temp.normalized_experiment_name(value JSONB) RETURNS TEXT
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    candidate TEXT;
BEGIN
    IF jsonb_typeof(value) IS DISTINCT FROM 'string' THEN
        RETURN NULL;
    END IF;
    candidate := value #>> '{}';
    IF candidate ~ E'[\\n\\r\\u000b\\f\u001c\u001d\u001e\u0085\u2028\u2029]' THEN
        RETURN NULL;
    END IF;
    candidate := btrim(candidate, E' \t\n\r\u000b\f\u001c\u001d\u001e\u001f\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000');
    IF candidate = '' OR char_length(candidate) > 120 THEN
        RETURN NULL;
    END IF;
    RETURN candidate;
END;
$$;

UPDATE backtest_runs SET name = COALESCE(
    pg_temp.normalized_experiment_name(request #> '{run_metadata,name}'),
    pg_temp.normalized_experiment_name(request #> '{run_metadata,label}')
) WHERE batch_id IS NULL;
UPDATE backtest_batches SET name = COALESCE(
    pg_temp.normalized_experiment_name(accepted_definition #> '{shared_request,run_metadata,name}'),
    pg_temp.normalized_experiment_name(accepted_definition #> '{shared_request,run_metadata,label}')
);

-- Disable only this request-immutability guard, under the transactional table
-- lock. Other data/constraints remain intact, and the guard is restored before
-- committing; no persistent bypass exists for ordinary writes.
ALTER TABLE backtest_runs DISABLE TRIGGER backtest_membership_guard;
UPDATE backtest_runs
SET request = jsonb_set(request, '{run_metadata}', (request->'run_metadata') - 'name' - 'label')
WHERE jsonb_typeof(request->'run_metadata') = 'object'
    AND (request->'run_metadata' ? 'name' OR request->'run_metadata' ? 'label');
ALTER TABLE backtest_runs ENABLE TRIGGER backtest_membership_guard;

UPDATE backtest_batches
SET accepted_definition = jsonb_set(accepted_definition, '{shared_request,run_metadata}',
    (accepted_definition #> '{shared_request,run_metadata}') - 'name' - 'label')
WHERE jsonb_typeof(accepted_definition #> '{shared_request,run_metadata}') = 'object'
    AND ((accepted_definition #> '{shared_request,run_metadata}') ? 'name'
        OR (accepted_definition #> '{shared_request,run_metadata}') ? 'label');

ALTER TABLE backtest_runs ADD CONSTRAINT backtest_run_experiment_name_check CHECK (
    name IS NULL OR (batch_id IS NULL AND char_length(name) BETWEEN 1 AND 120
        AND name = btrim(name, E' \t\n\r\u000b\f\u001c\u001d\u001e\u001f\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000')
        AND name !~ E'[\\n\\r\\u000b\\f\u001c\u001d\u001e\u0085\u2028\u2029]')
);
ALTER TABLE backtest_batches ADD CONSTRAINT backtest_batch_experiment_name_check CHECK (
    name IS NULL OR (char_length(name) BETWEEN 1 AND 120
        AND name = btrim(name, E' \t\n\r\u000b\f\u001c\u001d\u001e\u001f\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000')
        AND name !~ E'[\\n\\r\\u000b\\f\u001c\u001d\u001e\u0085\u2028\u2029]')
);
