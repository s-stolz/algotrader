from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
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


# Pending recovery is keyed by the logical Market/account M1 source only.

pending_recoveries = Table(
    "pending_recoveries",
    metadata,
    Column(
        "symbol_id", Integer, ForeignKey("markets.symbol_id", ondelete="CASCADE"), primary_key=True
    ),
    Column("account_id", String(128), primary_key=True),
    Column("recovery_id", String(36), nullable=False),
    Column("revision", BigInteger, nullable=False),
    Column("next_ms", BigInteger, nullable=False),
    Column("target_ms", BigInteger, nullable=False),
    Column("trigger", String(64), nullable=False),
    CheckConstraint("revision > 0"),
    CheckConstraint("next_ms >= 0 AND target_ms >= next_ms - 1"),
)


live_write_guards = Table(
    "live_write_guards",
    metadata,
    Column(
        "symbol_id", Integer, ForeignKey("markets.symbol_id", ondelete="CASCADE"), primary_key=True
    ),
    Column("account_id", String(128), primary_key=True),
    Column("write_id", String(36), nullable=False),
    Column("boundary_ms", BigInteger, nullable=False),
    CheckConstraint("boundary_ms >= 0"),
)
