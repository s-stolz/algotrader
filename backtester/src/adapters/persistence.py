"""Backtest run persistence adapters."""

from __future__ import annotations

import math
import sys
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol
from uuid import uuid4

from domain.types import (
    BACKTEST_RESULT_SCHEMA_VERSION,
    BacktestRequestSnapshot,
    BacktestResult,
    Fill,
    Trade,
)


class BacktestRunClient(Protocol):
    """Client protocol for durable run persistence through database-accessor-api."""

    def create_backtest_run(self, run: dict[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class BacktestPersistenceMetadata:
    run_id: str
    persisted_at: int


class BacktestRunPersistenceAdapter:
    """Maps a completed synchronous result to a terminal durable run."""

    def __init__(self, client: BacktestRunClient | None = None) -> None:
        self._client = client

    def save_run(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        run = build_succeeded_run_payload(
            result=result,
            execution_duration_ms=execution_duration_ms,
        )
        response = self._create_run(run)
        metadata = _metadata_from_response(response)
        return replace(
            result,
            backtest_run_id=metadata.run_id,
            persisted_at=metadata.persisted_at,
        )

    def _create_run(self, run: dict[str, Any]) -> Mapping[str, Any]:
        if self._client is not None:
            return self._client.create_backtest_run(run)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return client.create_backtest_run(run)


def build_succeeded_run_payload(
    *,
    result: BacktestResult,
    execution_duration_ms: int | None = None,
) -> dict[str, Any]:
    """Build one terminal succeeded-run payload for synchronous persistence."""

    persisted_at = _utc_now_text()
    diagnostics = deepcopy(result.diagnostics)
    diagnostics["execution_duration_ms"] = _execution_duration_ms(
        result=result,
        execution_duration_ms=execution_duration_ms,
    )
    request_snapshot = BacktestRequestSnapshot.from_request(result.request)

    return {
        "run_id": _new_run_id(),
        "status": "succeeded",
        "submitted_at": persisted_at,
        "started_at": persisted_at,
        "completed_at": persisted_at,
        "error_code": None,
        "error_message": None,
        "request_schema_version": request_snapshot.schema_version,
        "request": dict(request_snapshot.payload),
        "result_schema_version": BACKTEST_RESULT_SCHEMA_VERSION,
        "metrics": deepcopy(result.metrics),
        "diagnostics": diagnostics,
        "fills": [
            _fill_payload(sequence=sequence, fill=fill)
            for sequence, fill in enumerate(result.fills)
        ],
        "trades": [
            _closed_trade_payload(sequence=sequence, trade=trade)
            for sequence, trade in enumerate(result.trades)
        ],
    }


def _fill_payload(*, sequence: int, fill: Fill) -> dict[str, Any]:
    return {
        "fill_sequence": sequence,
        "timestamp_ms": int(fill.timestamp_ms),
        "symbol": str(fill.symbol),
        "side": _enum_or_text_value(fill.side),
        "quantity": float(fill.quantity),
        "price": float(fill.price),
        "fees": float(fill.fees),
        "exit_reason": (
            _enum_or_text_value(fill.exit_reason) if fill.exit_reason is not None else None
        ),
    }


def _closed_trade_payload(*, sequence: int, trade: Trade) -> dict[str, Any]:
    if trade.exit_timestamp_ms is None:
        raise ValueError("Cannot persist an open trade without exit_timestamp_ms")
    if trade.exit_price is None:
        raise ValueError("Cannot persist an open trade without exit_price")

    return {
        "trade_sequence": sequence,
        "trade_id": str(trade.trade_id),
        "symbol": str(trade.symbol),
        "quantity": float(trade.quantity),
        "entry_timestamp_ms": int(trade.entry_timestamp_ms),
        "entry_price": float(trade.entry_price),
        "exit_timestamp_ms": int(trade.exit_timestamp_ms),
        "exit_price": float(trade.exit_price),
        "realized_pnl": float(trade.realized_pnl),
        "fees": float(trade.fees),
        "exit_reason": _enum_or_text_value(trade.exit_reason),
    }


def _execution_duration_ms(
    *,
    result: BacktestResult,
    execution_duration_ms: int | None,
) -> int:
    if execution_duration_ms is None:
        execution_duration_ms = int(result.diagnostics.get("execution_duration_ms", 0))
    duration = int(execution_duration_ms)
    if duration < 0:
        raise ValueError("execution_duration_ms must be >= 0")
    return duration


def _metadata_from_response(response: Mapping[str, Any]) -> BacktestPersistenceMetadata:
    run_id = response.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("Backtest persistence response missing run_id")

    if "completed_at" not in response:
        raise ValueError("Backtest persistence response missing completed_at")

    return BacktestPersistenceMetadata(
        run_id=run_id,
        persisted_at=_timestamp_to_epoch_ms(response["completed_at"]),
    )


def _timestamp_to_epoch_ms(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("completed_at must be finite")
        return int(value)
    if isinstance(value, datetime):
        completed_at = value
    elif isinstance(value, str):
        completed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("completed_at must be an epoch millisecond value or datetime")

    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    return int(completed_at.timestamp() * 1000)


def _new_run_id() -> str:
    return str(uuid4())


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _import_database_accessor_client() -> type[Any]:
    try:
        from db_accessor_client import DatabaseAccessorClient
    except ModuleNotFoundError:
        _append_monorepo_lib_path("db_accessor_client")
        try:
            from db_accessor_client import DatabaseAccessorClient
        except ModuleNotFoundError as exc:
            raise RuntimeError("db_accessor_client is required for backtest persistence") from exc
    return DatabaseAccessorClient


def _append_monorepo_lib_path(lib_name: str) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    lib_path = repo_root / "libs" / lib_name
    as_text = str(lib_path)
    if lib_path.exists() and as_text not in sys.path:
        sys.path.append(as_text)


def _enum_or_text_value(value: object) -> str:
    return str(getattr(value, "value", value))
