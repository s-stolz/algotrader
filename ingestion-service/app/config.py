"""Configuration management for the ingestion service."""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone


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

    history_lookback_days: int | None = 90
    history_start_date: str | None = None

    def history_start_ms(self, now_ms: int) -> int:
        """Resolve and validate the inclusive UTC history boundary."""
        days = self.history_lookback_days
        start = self.history_start_date
        if (days is None) == (start is None):
            raise ValueError(
                "Set exactly one ingestion history option: lookback days or start date"
            )
        if days is not None:
            if type(days) is not int or days <= 0:
                raise ValueError("Ingestion history lookback days must be a positive integer")
            try:
                boundary = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc) - timedelta(
                    days=days
                )
            except OverflowError as exc:
                raise ValueError(
                    "Ingestion history lookback exceeds the supported date range"
                ) from exc
            return int(boundary.timestamp() * 1000)
        assert start is not None
        parsed = date.fromisoformat(start)
        if parsed.isoformat() != start:
            raise ValueError("Ingestion history start date must use YYYY-MM-DD")
        start_ms = int(
            datetime.combine(parsed, datetime.min.time(), timezone.utc).timestamp() * 1000
        )
        if start_ms > now_ms:
            raise ValueError("Ingestion history start date cannot be in the future")
        return start_ms

    @property
    def broker_service_base_url(self) -> str:
        """Full base URL for the broker service API."""
        return f"http://{self.broker_service_host}:{self.broker_service_port}"


def load_config() -> Config:
    """Load configuration from environment variables."""
    log_level = os.getenv("INGESTION_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO"))
    log_format = os.getenv("INGESTION_LOG_FORMAT", os.getenv("LOG_FORMAT", "pretty"))
    days = os.getenv("INGESTION_HISTORY_LOOKBACK_DAYS", "90").strip()
    start = os.getenv("INGESTION_HISTORY_START_DATE", "").strip()
    config = Config(
        history_lookback_days=int(days) if days else None,
        history_start_date=start or None,
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

    config.history_start_ms(int(datetime.now(timezone.utc).timestamp() * 1000))
    return config
