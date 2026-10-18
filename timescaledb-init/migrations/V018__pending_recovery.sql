CREATE TABLE pending_recoveries (
    symbol_id INTEGER NOT NULL REFERENCES markets(symbol_id) ON DELETE CASCADE,
    account_id VARCHAR(128) NOT NULL,
    recovery_id VARCHAR(36) NOT NULL,
    revision BIGINT NOT NULL CHECK (revision > 0),
    next_ms BIGINT NOT NULL,
    target_ms BIGINT NOT NULL,
    trigger VARCHAR(64) NOT NULL,
    PRIMARY KEY (symbol_id, account_id),
    CHECK (next_ms >= 0 AND target_ms >= next_ms - 1)
);
