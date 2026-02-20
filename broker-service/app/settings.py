from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CtraderCredentials(BaseSettings):
    client_id: str = Field(alias="CTRADER_CLIENT_ID")
    secret: str = Field(alias="CTRADER_SECRET")
    host_type: Literal["demo", "live"] = Field(alias="CTRADER_HOST_TYPE")
    access_token: str = Field(alias="CTRADER_ACCESS_TOKEN")

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


class Settings(BaseSettings):
    app_name: str = "broker-service"
    service_port: int = Field(default=8050, alias="BROKER_SERVICE_PORT")
    redis_url: str = Field(default="redis://redis:6379/0")
    tick_queue_size: int = 1000
    tick_stream_maxlen: int | None = None
    candle_stream_maxlen: int | None = None
    broker_max_symbol_streams: int = 20
    broker_max_trendbar_streams: int = 10
    log_level: str = "INFO"
    ctrader_request_timeout_seconds: float = 20.0

    model_config = SettingsConfigDict(
        env_prefix="BROKER_",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("tick_stream_maxlen", "candle_stream_maxlen", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        if value in ("", "none", "None", "null", "NULL"):
            return None
        return value

    def load_credentials(self) -> CtraderCredentials:
        return CtraderCredentials()  # type: ignore[call-arg]
