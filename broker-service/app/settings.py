from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


def _read_str(name: str, default: str | None = None) -> str:
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    return value


def _read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a float") from exc


def _read_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None:
        return None
    if value in ("", "none", "None", "null", "NULL"):
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer or empty") from exc


@dataclass(frozen=True, slots=True)
class CtraderCredentials:
    client_id: str
    secret: str
    host_type: Literal["demo", "live"]
    access_token: str
    refresh_token: str
    token_url: str
    access_token_expires_in_seconds: int
    token_request_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "CtraderCredentials":
        host_type = _read_str("CTRADER_HOST_TYPE").lower()
        if host_type not in {"demo", "live"}:
            raise ValueError("CTRADER_HOST_TYPE must be one of: demo, live")

        return cls(
            client_id=_read_str("CTRADER_CLIENT_ID"),
            secret=_read_str("CTRADER_SECRET"),
            host_type=host_type,  # type: ignore[arg-type]
            access_token=_read_str("CTRADER_ACCESS_TOKEN"),
            refresh_token=_read_str("CTRADER_REFRESH_TOKEN"),
            token_url=_read_str("CTRADER_TOKEN_URL", "https://openapi.ctrader.com/apps/token"),
            access_token_expires_in_seconds=_read_int(
                "CTRADER_ACCESS_TOKEN_EXPIRES_IN_SECONDS",
                2628000,
            ),
            token_request_timeout_seconds=_read_float(
                "CTRADER_TOKEN_REQUEST_TIMEOUT_SECONDS",
                10.0,
            ),
        )


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "broker-service"
    service_port: int = 8050
    redis_url: str = "redis://redis:6379/0"
    tick_queue_size: int = 1000
    tick_stream_maxlen: int | None = None
    candle_stream_maxlen: int | None = None
    broker_max_symbol_streams: int = 20
    broker_max_trendbar_streams: int = 10
    broker_token_redis_key: str = "broker:auth:ctrader:current"
    broker_token_refresh_early_seconds: int = 604800
    broker_token_refresh_retry_delay_seconds: int = 30
    broker_token_refresh_max_retries: int = 3
    log_level: str = "INFO"
    log_format: str = "pretty"
    ctrader_request_timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=_read_str("BROKER_APP_NAME", "broker-service"),
            service_port=_read_int("BROKER_SERVICE_PORT", 8050),
            redis_url=_read_str("BROKER_REDIS_URL", "redis://redis:6379/0"),
            tick_queue_size=_read_int("BROKER_TICK_QUEUE_SIZE", 1000),
            tick_stream_maxlen=_read_optional_int("BROKER_TICK_STREAM_MAXLEN"),
            candle_stream_maxlen=_read_optional_int("BROKER_CANDLE_STREAM_MAXLEN"),
            broker_max_symbol_streams=_read_int("BROKER_MAX_SYMBOL_STREAMS", 20),
            broker_max_trendbar_streams=_read_int("BROKER_MAX_TRENDBAR_STREAMS", 10),
            broker_token_redis_key=_read_str(
                "BROKER_TOKEN_REDIS_KEY",
                "broker:auth:ctrader:current",
            ),
            broker_token_refresh_early_seconds=_read_int(
                "BROKER_TOKEN_REFRESH_EARLY_SECONDS",
                604800,
            ),
            broker_token_refresh_retry_delay_seconds=_read_int(
                "BROKER_TOKEN_REFRESH_RETRY_DELAY_SECONDS",
                30,
            ),
            broker_token_refresh_max_retries=_read_int(
                "BROKER_TOKEN_REFRESH_MAX_RETRIES",
                3,
            ),
            log_level=_read_str("BROKER_LOG_LEVEL", "INFO"),
            log_format=_read_str("BROKER_LOG_FORMAT", "pretty"),
            ctrader_request_timeout_seconds=_read_float(
                "BROKER_CTRADER_REQUEST_TIMEOUT_SECONDS", 20.0
            ),
        )

    def load_credentials(self) -> CtraderCredentials:
        return CtraderCredentials.from_env()
