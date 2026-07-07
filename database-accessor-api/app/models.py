from sqlalchemy import (
    JSON,
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

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

json_document = JSON().with_variant(JSONB(), "postgresql")

backtest_runs = Table(
    "backtest_runs",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column("status", String(16), nullable=False),
    Column("submitted_at", TIMESTAMP(timezone=True), nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("request_schema_version", Integer, nullable=False),
    Column("request", json_document, nullable=False),
    Column("result_schema_version", Integer, nullable=True),
    Column("metrics", json_document, nullable=True),
    Column("diagnostics", json_document, nullable=True),
    CheckConstraint(
        "status IN ('queued', 'running', 'succeeded', 'failed')",
        name="backtest_runs_status_check",
    ),
    Index("idx_backtest_runs_submitted_at", "submitted_at", "run_id"),
    Index("idx_backtest_runs_status_submitted_at", "status", "submitted_at", "run_id"),
)

backtest_fills = Table(
    "backtest_fills",
    metadata,
    Column(
        "run_id",
        String(36),
        ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("fill_sequence", Integer, nullable=False),
    Column("timestamp_ms", BigInteger, nullable=False),
    Column("symbol", String(32), nullable=False),
    Column("side", String(8), nullable=False),
    Column("quantity", Float, nullable=False),
    Column("price", Float, nullable=False),
    Column("fees", Float, nullable=False),
    Column("exit_reason", String(32), nullable=True),
    PrimaryKeyConstraint("run_id", "fill_sequence"),
    CheckConstraint("side IN ('buy', 'sell')", name="backtest_fills_side_check"),
    CheckConstraint(
        "exit_reason IS NULL OR " "exit_reason IN ('signal', 'stop_loss', 'take_profit')",
        name="backtest_fills_exit_reason_check",
    ),
    Index(
        "idx_backtest_fills_run_order",
        "run_id",
        "timestamp_ms",
        "fill_sequence",
    ),
)

backtest_closed_trades = Table(
    "backtest_closed_trades",
    metadata,
    Column(
        "run_id",
        String(36),
        ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("trade_sequence", Integer, nullable=False),
    Column("trade_id", String(64), nullable=False),
    Column("symbol", String(32), nullable=False),
    Column("trade_direction", String(8), nullable=False),
    Column("quantity", Float, nullable=False),
    Column("entry_timestamp_ms", BigInteger, nullable=False),
    Column("entry_price", Float, nullable=False),
    Column("exit_timestamp_ms", BigInteger, nullable=False),
    Column("exit_price", Float, nullable=False),
    Column("stop_loss_price", Float, nullable=True),
    Column("take_profit_price", Float, nullable=True),
    Column("realized_pnl", Float, nullable=False),
    Column("fees", Float, nullable=False),
    Column("exit_reason", String(32), nullable=False),
    PrimaryKeyConstraint("run_id", "trade_sequence"),
    UniqueConstraint("run_id", "trade_id", name="uq_backtest_closed_trades_identity"),
    CheckConstraint(
        "exit_reason IN ('signal', 'stop_loss', 'take_profit')",
        name="backtest_closed_trades_exit_reason_check",
    ),
    CheckConstraint(
        "trade_direction IN ('long', 'short')",
        name="backtest_closed_trades_trade_direction_check",
    ),
    Index(
        "idx_backtest_closed_trades_run_order",
        "run_id",
        "entry_timestamp_ms",
        "exit_timestamp_ms",
        "trade_sequence",
    ),
)
