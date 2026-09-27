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
    func,
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

backtest_batches = Table(
    "backtest_batches",
    metadata,
    Column("batch_id", String(36), primary_key=True),
    Column("submission_id", String(36), nullable=False, unique=True),
    Column("status", String(16), nullable=False),
    Column("accepted_at", TIMESTAMP(timezone=True), nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("cancel_requested_at", TIMESTAMP(timezone=True), nullable=True),
    Column("cancellation_source", String(32), nullable=True),
    Column("cancellation_reason", Text, nullable=True),
    Column("lifecycle_revision", Integer, nullable=False),
    Column("definition_schema_version", Integer, nullable=False),
    Column("accepted_definition", json_document, nullable=False),
    Column("strategy_metadata", json_document, nullable=False),
    Column("raw_count", Integer, nullable=False),
    Column("member_count", Integer, nullable=False),
    Column("excluded_count", Integer, nullable=False),
    CheckConstraint("raw_count = member_count + excluded_count", name="batch_counts_check"),
    CheckConstraint(
        "(cancel_requested_at IS NULL AND cancellation_source IS NULL "
        "AND cancellation_reason IS NULL) OR "
        "(cancel_requested_at IS NOT NULL AND cancellation_source IS NOT NULL "
        "AND cancellation_reason IS NOT NULL)",
        name="backtest_batch_cancellation_check",
    ),
)

backtest_runs = Table(
    "backtest_runs",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column("status", String(16), nullable=False),
    Column("submitted_at", TIMESTAMP(timezone=True), nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("cancel_requested_at", TIMESTAMP(timezone=True), nullable=True),
    Column("cancellation_source", String(32), nullable=True),
    Column("cancellation_reason", Text, nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("request_schema_version", Integer, nullable=False),
    Column("request", json_document, nullable=False),
    Column("result_schema_version", Integer, nullable=True),
    Column("metrics", json_document, nullable=True),
    Column("diagnostics", json_document, nullable=True),
    Column("replay_descriptor", json_document, nullable=True),
    Column(
        "batch_id",
        String(36),
        ForeignKey("backtest_batches.batch_id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("member_ordinal", Integer, nullable=True),
    CheckConstraint(
        "status IN ('queued', 'running', 'cancelling', 'succeeded', 'failed', 'cancelled')",
        name="backtest_runs_status_check",
    ),
    CheckConstraint(
        "(cancel_requested_at IS NULL AND cancellation_source IS NULL "
        "AND cancellation_reason IS NULL) "
        "OR (cancel_requested_at IS NOT NULL AND cancellation_source IS NOT NULL "
        "AND cancellation_reason IS NOT NULL)",
        name="backtest_run_cancellation_check",
    ),
    CheckConstraint(
        "(status NOT IN ('cancelling', 'cancelled') OR cancel_requested_at IS NOT NULL) "
        "AND (status <> 'cancelling' OR completed_at IS NULL) "
        "AND (status <> 'cancelled' OR completed_at IS NOT NULL)",
        name="backtest_run_cancel_status_check",
    ),
    Index("idx_backtest_runs_submitted_at", "submitted_at", "run_id"),
    Index("idx_backtest_runs_status_submitted_at", "status", "submitted_at", "run_id"),
    Index("uq_backtest_batch_ordinal", "batch_id", "member_ordinal", unique=True),
    CheckConstraint(
        "(batch_id IS NULL AND member_ordinal IS NULL) OR "
        "(batch_id IS NOT NULL AND member_ordinal >= 0)",
        name="backtest_member_identity_check",
    ),
)

backtest_batch_events = Table(
    "backtest_batch_events",
    metadata,
    Column(
        "batch_id",
        String(36),
        ForeignKey("backtest_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("revision", Integer, nullable=False),
    Column("event_type", String(32), nullable=False),
    Column("prior_status", String(16), nullable=True),
    Column("status", String(16), nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), nullable=False),
    Column("reason", Text, nullable=True),
    Column("trigger_run_id", String(36), nullable=True),
    Column("command_id", String(36), nullable=True),
    PrimaryKeyConstraint("batch_id", "revision"),
    Index("uq_backtest_batch_command", "batch_id", "command_id", unique=True),
)

backtest_batch_commands = Table(
    "backtest_batch_commands",
    metadata,
    Column(
        "batch_id",
        String(36),
        ForeignKey("backtest_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("command_id", String(36), nullable=False),
    Column("command", String(16), nullable=False),
    Column("status", String(16), nullable=False),
    Column("lifecycle_revision", Integer, nullable=False),
    Column("occurred_at", TIMESTAMP(timezone=True), nullable=False),
    PrimaryKeyConstraint("batch_id", "command_id"),
    CheckConstraint(
        "command IN ('pause', 'resume', 'cancel')", name="backtest_batch_command_type_check"
    ),
)

backtest_execution_slot = Table(
    "backtest_execution_slot",
    metadata,
    Column("slot_id", Integer, primary_key=True),
    Column("owner_token", String(36), nullable=True),
    Column("run_id", String(36), ForeignKey("backtest_runs.run_id"), nullable=True),
    Column("fault_code", String(64), nullable=True),
    Column("fault_message", Text, nullable=True),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("slot_id = 1", name="backtest_execution_slot_id_check"),
    CheckConstraint(
        "(owner_token IS NULL) = (run_id IS NULL)",
        name="backtest_execution_slot_owner_pair_check",
    ),
)

backtest_queue_turns = Table(
    "backtest_queue_turns",
    metadata,
    Column(
        "turn_id",
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    Column("run_id", String(36), ForeignKey("backtest_runs.run_id"), nullable=True),
    Column(
        "batch_id",
        String(36),
        ForeignKey("backtest_batches.batch_id", ondelete="CASCADE"),
        nullable=True,
    ),
    CheckConstraint(
        "(run_id IS NULL) <> (batch_id IS NULL)", name="backtest_queue_turn_identity_check"
    ),
    Index("uq_backtest_queue_standalone", "run_id", unique=True),
    Index("uq_backtest_queue_batch", "batch_id", unique=True),
)

backtest_worker_heartbeats = Table(
    "backtest_worker_heartbeats",
    metadata,
    Column("worker_id", String(36), primary_key=True),
    Column("owner_token", String(36), nullable=True),
    Column("heartbeat_at", TIMESTAMP(timezone=True), nullable=False),
    Column("fault_code", String(64), nullable=True),
    Column("fault_message", Text, nullable=True),
    Index("idx_backtest_worker_heartbeats_recent", "heartbeat_at"),
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
        "exit_reason IS NULL OR exit_reason IN ('signal', 'stop_loss', 'take_profit')",
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
