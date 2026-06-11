"""Backtest run persistence adapters."""

from __future__ import annotations

import math
import sys
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from uuid import uuid4

from db_accessor_client import DatabaseAccessorClientError
from domain.enums import BacktestRunStatus, ExitReason, OrderSide
from domain.types import (
    BACKTEST_RESULT_SCHEMA_VERSION,
    BacktestFillRecord,
    BacktestRequestSnapshot,
    BacktestResult,
    BacktestRunQuery,
    BacktestRunRecord,
    BacktestTradeRecord,
    Fill,
    Trade,
)


class BacktestRunClient(Protocol):
    """Client protocol for durable run persistence through database-accessor-api."""

    def create_backtest_run(self, run: dict[str, Any]) -> Mapping[str, Any]: ...


class BacktestRunRepositoryClient(BacktestRunClient, Protocol):
    """Client protocol for queued run creation and status retrieval."""

    def get_backtest_run(self, run_id: str) -> Mapping[str, Any]: ...

    def list_backtest_runs(self, **query: Any) -> Sequence[Mapping[str, Any]]: ...

    def get_backtest_fills(self, run_id: str) -> Sequence[Mapping[str, Any]]: ...

    def get_backtest_trades(self, run_id: str) -> Sequence[Mapping[str, Any]]: ...

    def delete_backtest_run(self, run_id: str) -> None: ...


class BacktestLifecycleClient(Protocol):
    """Client protocol for lifecycle and transactional result persistence."""

    def conditional_update_backtest_run(
        self,
        run_id: str,
        update: dict[str, Any],
    ) -> bool: ...

    def complete_backtest_run(
        self,
        run_id: str,
        completion: dict[str, Any],
    ) -> bool: ...


@dataclass(frozen=True)
class BacktestPersistenceMetadata:
    run_id: str
    persisted_at: int


class DatabaseAccessorBacktestRunRepository:
    """Maps durable run domain records to the database-accessor client contract."""

    def __init__(self, client: BacktestRunRepositoryClient | None = None) -> None:
        self._client = client

    def create(self, run: BacktestRunRecord) -> BacktestRunRecord:
        response = self._create_run(_run_record_payload(run))
        return _run_record_from_response(response)

    def get(self, run_id: str) -> BacktestRunRecord | None:
        try:
            response = self._get_run(run_id)
        except DatabaseAccessorClientError as exc:
            if exc.status_code == 404:
                return None
            raise
        return _run_record_from_response(response)

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        responses = self._list_runs(_run_query_params(query))
        return [_run_record_from_response(response) for response in responses]

    def get_fills(self, run_id: str) -> list[BacktestFillRecord]:
        return [_fill_record_from_response(response) for response in self._get_fills(run_id)]

    def get_trades(self, run_id: str) -> list[BacktestTradeRecord]:
        return [_trade_record_from_response(response) for response in self._get_trades(run_id)]

    def delete(self, run_id: str) -> bool:
        try:
            self._delete_run(run_id)
        except DatabaseAccessorClientError as exc:
            if exc.status_code == 404:
                return False
            raise
        return True

    def _create_run(self, run: dict[str, Any]) -> Mapping[str, Any]:
        if self._client is not None:
            return self._client.create_backtest_run(run)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return client.create_backtest_run(run)

    def _get_run(self, run_id: str) -> Mapping[str, Any]:
        if self._client is not None:
            return self._client.get_backtest_run(run_id)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return client.get_backtest_run(run_id)

    def _list_runs(self, query: dict[str, Any]) -> Sequence[Mapping[str, Any]]:
        if self._client is not None:
            return self._client.list_backtest_runs(**query)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return client.list_backtest_runs(**query)

    def _get_fills(self, run_id: str) -> Sequence[Mapping[str, Any]]:
        if self._client is not None:
            return self._client.get_backtest_fills(run_id)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return client.get_backtest_fills(run_id)

    def _get_trades(self, run_id: str) -> Sequence[Mapping[str, Any]]:
        if self._client is not None:
            return self._client.get_backtest_trades(run_id)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return client.get_backtest_trades(run_id)

    def _delete_run(self, run_id: str) -> None:
        if self._client is not None:
            self._client.delete_backtest_run(run_id)
            return

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            client.delete_backtest_run(run_id)


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


class BacktestRunLifecyclePersistenceAdapter:
    """Maps canonical domain results to primitive durable lifecycle operations."""

    def __init__(self, client: BacktestLifecycleClient | None = None) -> None:
        self._client = client

    def conditional_update(
        self,
        *,
        run_id: str,
        expected_status: BacktestRunStatus,
        new_status: BacktestRunStatus,
        started_at_ms: int | None = None,
        completed_at_ms: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> bool:
        update = {
            "expected_status": _enum_or_text_value(expected_status),
            "new_status": _enum_or_text_value(new_status),
        }
        if started_at_ms is not None:
            update["started_at"] = _epoch_ms_to_utc_text(started_at_ms)
        if completed_at_ms is not None:
            update["completed_at"] = _epoch_ms_to_utc_text(completed_at_ms)
        if error_code is not None:
            update["error_code"] = error_code
        if error_message is not None:
            update["error_message"] = error_message
        return self._conditional_update(run_id, update)

    def complete(
        self,
        *,
        run_id: str,
        expected_status: BacktestRunStatus,
        completed_at_ms: int,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> bool:
        completion = build_successful_completion_payload(
            expected_status=expected_status,
            completed_at_ms=completed_at_ms,
            result=result,
            execution_duration_ms=execution_duration_ms,
        )
        return self._complete(run_id, completion)

    def _conditional_update(self, run_id: str, update: dict[str, Any]) -> bool:
        if self._client is not None:
            return self._client.conditional_update_backtest_run(run_id, update)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return bool(client.conditional_update_backtest_run(run_id, update))

    def _complete(self, run_id: str, completion: dict[str, Any]) -> bool:
        if self._client is not None:
            return self._client.complete_backtest_run(run_id, completion)

        client_cls = _import_database_accessor_client()
        with client_cls() as client:
            return bool(client.complete_backtest_run(run_id, completion))


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
    artifacts = _result_artifact_payload(result)

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
        **artifacts,
    }


def build_successful_completion_payload(
    *,
    expected_status: BacktestRunStatus,
    completed_at_ms: int,
    result: BacktestResult,
    execution_duration_ms: int | None = None,
) -> dict[str, Any]:
    """Build the atomic completion payload without the non-persisted equity curve."""

    diagnostics = deepcopy(result.diagnostics)
    diagnostics["execution_duration_ms"] = _execution_duration_ms(
        result=result,
        execution_duration_ms=execution_duration_ms,
    )
    return {
        "expected_status": _enum_or_text_value(expected_status),
        "completed_at": _epoch_ms_to_utc_text(completed_at_ms),
        "result_schema_version": BACKTEST_RESULT_SCHEMA_VERSION,
        "metrics": deepcopy(result.metrics),
        "diagnostics": diagnostics,
        **_result_artifact_payload(result),
    }


def _run_record_payload(run: BacktestRunRecord) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "status": _enum_or_text_value(run.status),
        "submitted_at": _epoch_ms_to_utc_text(run.submitted_at_ms),
        "started_at": (
            _epoch_ms_to_utc_text(run.started_at_ms) if run.started_at_ms is not None else None
        ),
        "completed_at": (
            _epoch_ms_to_utc_text(run.completed_at_ms) if run.completed_at_ms is not None else None
        ),
        "error_code": run.error_code,
        "error_message": run.error_message,
        "request_schema_version": run.request_snapshot.schema_version,
        "request": deepcopy(dict(run.request_snapshot.payload)),
        "result_schema_version": run.result_schema_version,
        "metrics": deepcopy(run.metrics),
        "diagnostics": deepcopy(run.diagnostics),
        "fills": [],
        "trades": [],
    }


def _run_query_params(query: BacktestRunQuery) -> dict[str, Any]:
    params = {
        "status": (_enum_or_text_value(query.status) if query.status is not None else None),
        "symbol": query.symbol,
        "timeframe": query.timeframe,
        "strategy": query.strategy_id,
        "engine": (_enum_or_text_value(query.engine) if query.engine is not None else None),
        "submitted_from": (
            _epoch_ms_to_utc_text(query.submitted_from_ms)
            if query.submitted_from_ms is not None
            else None
        ),
        "submitted_to": (
            _epoch_ms_to_utc_text(query.submitted_to_ms)
            if query.submitted_to_ms is not None
            else None
        ),
    }
    return {name: value for name, value in params.items() if value is not None}


def _run_record_from_response(response: Mapping[str, Any]) -> BacktestRunRecord:
    request = response.get("request")
    if not isinstance(request, Mapping):
        raise ValueError("Backtest run response missing request")

    request_snapshot = BacktestRequestSnapshot(
        schema_version=int(response["request_schema_version"]),
        payload=deepcopy(dict(request)),
    )
    request_snapshot.to_request()

    return BacktestRunRecord(
        run_id=str(response["run_id"]),
        status=BacktestRunStatus(str(response["status"])),
        submitted_at_ms=_timestamp_to_epoch_ms(response["submitted_at"]),
        started_at_ms=_optional_timestamp_to_epoch_ms(response.get("started_at")),
        completed_at_ms=_optional_timestamp_to_epoch_ms(response.get("completed_at")),
        error_code=_optional_text(response.get("error_code")),
        error_message=_optional_text(response.get("error_message")),
        request_snapshot=request_snapshot,
        result_schema_version=(
            int(response["result_schema_version"])
            if response.get("result_schema_version") is not None
            else None
        ),
        metrics=_optional_mapping(response.get("metrics")),
        diagnostics=_optional_mapping(response.get("diagnostics")),
    )


def _fill_record_from_response(response: Mapping[str, Any]) -> BacktestFillRecord:
    exit_reason = response.get("exit_reason")
    return BacktestFillRecord(
        run_id=str(response["run_id"]),
        sequence=int(response["fill_sequence"]),
        timestamp_ms=int(response["timestamp_ms"]),
        symbol=str(response["symbol"]),
        side=OrderSide(str(response["side"])),
        quantity=float(response["quantity"]),
        price=float(response["price"]),
        fees=float(response["fees"]),
        exit_reason=(ExitReason(str(exit_reason)) if exit_reason is not None else None),
    )


def _trade_record_from_response(response: Mapping[str, Any]) -> BacktestTradeRecord:
    return BacktestTradeRecord(
        run_id=str(response["run_id"]),
        sequence=int(response["trade_sequence"]),
        trade_id=str(response["trade_id"]),
        symbol=str(response["symbol"]),
        quantity=float(response["quantity"]),
        entry_timestamp_ms=int(response["entry_timestamp_ms"]),
        entry_price=float(response["entry_price"]),
        exit_timestamp_ms=int(response["exit_timestamp_ms"]),
        exit_price=float(response["exit_price"]),
        realized_pnl=float(response["realized_pnl"]),
        fees=float(response["fees"]),
        exit_reason=ExitReason(str(response["exit_reason"])),
    )


def _result_artifact_payload(result: BacktestResult) -> dict[str, Any]:
    return {
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


def _optional_timestamp_to_epoch_ms(value: Any) -> int | None:
    if value is None:
        return None
    return _timestamp_to_epoch_ms(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_mapping(value: Any) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("Backtest run response artifact must be an object")
    return deepcopy(dict(value))


def _epoch_ms_to_utc_text(value: int) -> str:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()


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
