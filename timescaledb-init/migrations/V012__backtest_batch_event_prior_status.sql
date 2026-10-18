-- Existing events have no recorded prior state; leave their history intact.
ALTER TABLE backtest_batch_events
    ADD COLUMN prior_status VARCHAR(16);
