-- Create markets table
CREATE TABLE IF NOT EXISTS markets (
    symbol_id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    market_type VARCHAR(20) NOT NULL,
    min_move FLOAT NOT NULL
);

-- Create candles table
CREATE TABLE IF NOT EXISTS candles (
    symbol_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    volume FLOAT NOT NULL,
    FOREIGN KEY (symbol_id) REFERENCES markets (symbol_id),
    PRIMARY KEY (symbol_id, timestamp)
);
