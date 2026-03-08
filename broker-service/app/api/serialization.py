from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from app.api.contracts import SymbolLightBody, TickStreamStatusBody, TrendbarStreamStatusBody
from app.domain.models import Symbol
from app.domain.value_objects import SymbolDescriptor


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_jsonable(val) for key, val in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    return value


def serialize_symbol_light(symbol: SymbolDescriptor) -> SymbolLightBody:
    return {
        "symbolId": int(symbol.symbol_id),
        "symbolName": symbol.symbol_name,
        "enabled": symbol.enabled,
    }


def serialize_tick_stream_status(status: Any) -> TickStreamStatusBody:
    return {
        "running": status.running,
        "startedAt": status.started_at,
        "lastTickAt": status.last_tick_at,
        "uptimeSeconds": status.uptime_seconds,
        "error": status.error,
    }


def serialize_trendbar_stream_status(status: Any) -> TrendbarStreamStatusBody:
    return {
        "running": status.running,
        "startedAt": status.started_at,
        "lastBarAt": status.last_bar_at,
        "uptimeSeconds": status.uptime_seconds,
        "error": status.error,
    }


def serialize_symbol(symbol: Symbol) -> dict[str, Any]:
    return to_jsonable(symbol)
