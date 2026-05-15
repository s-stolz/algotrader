from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
)

metadata = MetaData()

markets = Table(
    "markets",
    metadata,
    Column("symbol_id", Integer, primary_key=True, index=True),
    Column("symbol", String(10), nullable=False),
    Column("exchange", String(20), nullable=False),
    Column("market_type", String(20), nullable=False),
    Column("min_move", Float, nullable=False),
    Column("timezone", String(64), nullable=False, server_default="UTC"),
)

candles = Table(
    "candles",
    metadata,
    Column("symbol_id", Integer, ForeignKey("markets.symbol_id"), nullable=False),
    Column("timestamp_utc", TIMESTAMP(timezone=True), nullable=False),
    Column("open", Float, nullable=False),
    Column("high", Float, nullable=False),
    Column("low", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Float, nullable=False),
    PrimaryKeyConstraint("symbol_id", "timestamp_utc"),
)

backtest_run_summaries = Table(
    "backtest_run_summaries",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column("persisted_at", TIMESTAMP(timezone=True), nullable=False),
    Column("execution_duration_ms", Integer, nullable=False),
    Column("symbol", String(32), nullable=False),
    Column("timeframe", String(16), nullable=False),
    Column("engine", String(32), nullable=False),
    Column("strategy_id", String(128), nullable=False),
    Column("start_ms", BigInteger, nullable=False),
    Column("end_ms", BigInteger, nullable=False),
    Column("initial_capital", Float, nullable=False),
    Column("final_equity", Float, nullable=False),
    Column("final_cash", Float, nullable=False),
    Column("final_position_symbol", String(32), nullable=True),
    Column("final_position_quantity", Float, nullable=False),
    Column("total_return_pct", Float, nullable=False),
    Column("max_drawdown_pct", Float, nullable=False),
    Column("trade_count", Integer, nullable=False),
)
