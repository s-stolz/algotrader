"""Configuration management for the ingestion service."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Config:
    """Service configuration loaded from environment variables."""

    redis_url: str
    broker_service_host: str
    broker_service_port: int
    broker_account_id: str
    log_level: str
    log_format: str
    consumer_batch_size: int
    consumer_block_ms: int
    startup_watermark_concurrency: int
    startup_stream_start_concurrency: int
    startup_backfill_concurrency: int
    broker_health_poll_seconds: int
    recovery_backoff_initial_seconds: int
    recovery_backoff_max_seconds: int

    history_lookback_days: int | None = 365 * 5
    history_start_date: str | None = None

    def history_start_ms(self, now_ms: int) -> int:
        if self.history_start_date is not None:
            value = datetime.strptime(self.history_start_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            start = int(value.timestamp() * 1000)
            if start > now_ms or start < 0:
                raise ValueError("History start date must be between epoch and today UTC")
            return start
        if self.history_lookback_days is None or self.history_lookback_days < 1:
            raise ValueError("History lookback must be a positive number of days")
        return max(0, now_ms - self.history_lookback_days * 86400000)

    @property
    def broker_service_base_url(self) -> str:
        """Full base URL for the broker service API."""
        return f"http://{self.broker_service_host}:{self.broker_service_port}"


def load_config() -> Config:
    """Load configuration from environment variables."""
    log_level = os.getenv("INGESTION_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO"))
    log_format = os.getenv("INGESTION_LOG_FORMAT", os.getenv("LOG_FORMAT", "pretty"))
    lookback = os.getenv("HISTORY_LOOKBACK_DAYS")
    start_date = os.getenv("HISTORY_START_DATE")
    if lookback and start_date:
        raise ValueError("Choose HISTORY_LOOKBACK_DAYS or HISTORY_START_DATE")
    return Config(
        history_lookback_days=int(lookback) if lookback else (None if start_date else 365 * 5),
        history_start_date=start_date or None,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        broker_service_host=os.getenv("BROKER_SERVICE_HOST", "broker-service"),
        broker_service_port=int(os.getenv("BROKER_SERVICE_PORT", "8050")),
        broker_account_id=os.getenv("ACCOUNT_ID", "12345"),
        log_level=log_level,
        log_format=log_format,
        consumer_batch_size=int(os.getenv("CONSUMER_BATCH_SIZE", "100")),
        consumer_block_ms=int(os.getenv("CONSUMER_BLOCK_MS", "5000")),
        startup_watermark_concurrency=int(os.getenv("STARTUP_WATERMARK_CONCURRENCY", "2")),
        startup_stream_start_concurrency=int(os.getenv("STARTUP_STREAM_START_CONCURRENCY", "8")),
        startup_backfill_concurrency=int(os.getenv("STARTUP_BACKFILL_CONCURRENCY", "4")),
        broker_health_poll_seconds=int(os.getenv("BROKER_HEALTH_POLL_SECONDS", "10")),
        recovery_backoff_initial_seconds=int(os.getenv("RECOVERY_BACKOFF_INITIAL_SECONDS", "5")),
        recovery_backoff_max_seconds=int(os.getenv("RECOVERY_BACKOFF_MAX_SECONDS", "300")),
    )
