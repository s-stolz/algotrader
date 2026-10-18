CREATE TABLE live_write_guards (
    symbol_id INTEGER NOT NULL REFERENCES markets(symbol_id) ON DELETE CASCADE,
    account_id VARCHAR(128) NOT NULL,
    write_id VARCHAR(36) NOT NULL,
    boundary_ms BIGINT NOT NULL CHECK (boundary_ms >= 0),
    PRIMARY KEY (symbol_id, account_id)
);
