from sqlalchemy import (
    Table, Column, Integer, String, Float, TIMESTAMP, ForeignKey,
    MetaData, PrimaryKeyConstraint
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
)

candles = Table(
    "candles",
    metadata,
    Column("symbol_id", Integer, ForeignKey(
        "markets.symbol_id"), nullable=False),
    Column("timestamp", TIMESTAMP, nullable=False),
    Column("open", Float, nullable=False),
    Column("high", Float, nullable=False),
    Column("low", Float, nullable=False),
    Column("close", Float, nullable=False),
    Column("volume", Float, nullable=False),
    PrimaryKeyConstraint("symbol_id", "timestamp")
)
