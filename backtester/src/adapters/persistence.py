"""Backtest result persistence adapters."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from domain.enums import BacktestEngine
from domain.types import BacktestResult, PortfolioSnapshot, Trade


class BacktestRunSummaryClient(Protocol):
    """Client protocol for run-summary persistence through database-accessor-api."""

    def store_backtest_run_summary(self, summary: dict[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class BacktestPersistenceMetadata:
    run_id: str
    persisted_at: int


class BacktestRunSummaryPersistenceAdapter:
    """Maps completed backtest results to database-accessor run summaries."""

    def __init__(self, client: BacktestRunSummaryClient) -> None:
        self._client = client

    def save_run_summary(
        self,
        *,
        result: BacktestResult,
        execution_duration_ms: int | None = None,
    ) -> BacktestResult:
        summary = build_run_summary_payload(
            result=result,
            execution_duration_ms=execution_duration_ms,
        )
        response = self._client.store_backtest_run_summary(summary)
        metadata = _metadata_from_response(response)
        return replace(
            result,
            backtest_run_id=metadata.run_id,
            persisted_at=metadata.persisted_at,
        )


def build_run_summary_payload(
    *,
    result: BacktestResult,
    execution_duration_ms: int | None = None,
) -> dict[str, Any]:
    """Build the compact database-accessor run-summary payload for a result."""

    request = result.request
    symbol = _single_run_symbol(result)
    final_snapshot = _final_portfolio_snapshot(result)
    final_position_symbol, final_position_quantity = _final_open_exposure(
        result=result,
        final_snapshot=final_snapshot,
    )

    payload = {
        "execution_duration_ms": _execution_duration_ms(
            result=result,
            execution_duration_ms=execution_duration_ms,
        ),
        "symbol": symbol,
        "timeframe": str(request.timeframe),
        "engine": _engine_value(request.engine),
        "strategy_id": str(request.strategy.strategy_id),
        "start_ms": int(request.start_ms),
        "end_ms": int(request.end_ms),
        "initial_capital": float(request.initial_capital),
        "final_equity": float(final_snapshot.equity),
        "final_cash": float(final_snapshot.cash),
        "final_position_symbol": final_position_symbol,
        "final_position_quantity": final_position_quantity,
        "total_return_pct": _metric_float(result, "total_return_pct"),
        "max_drawdown_pct": _metric_float(result, "max_drawdown_pct"),
        "trade_count": _metric_int(result, "trade_count"),
    }
    trades = build_closed_trade_payloads(result)
    if trades:
        payload["trades"] = trades
    return payload


def build_closed_trade_payloads(result: BacktestResult) -> list[dict[str, Any]]:
    """Build database-accessor payload rows for closed trades in a result."""

    return [_closed_trade_payload(trade) for trade in result.trades]


def _closed_trade_payload(trade: Trade) -> dict[str, Any]:
    if trade.exit_timestamp_ms is None:
        raise ValueError("Cannot persist an open trade without exit_timestamp_ms")
    if trade.exit_price is None:
        raise ValueError("Cannot persist an open trade without exit_price")

    return {
        "trade_id": str(trade.trade_id),
        "symbol": str(trade.symbol),
        "quantity": float(trade.quantity),
        "entry_timestamp_ms": int(trade.entry_timestamp_ms),
        "entry_price": float(trade.entry_price),
        "exit_timestamp_ms": int(trade.exit_timestamp_ms),
        "exit_price": float(trade.exit_price),
        "realized_pnl": float(trade.realized_pnl),
        "fees": float(trade.fees),
    }


def _single_run_symbol(result: BacktestResult) -> str:
    symbols = [str(symbol) for symbol in result.request.symbols]
    if len(symbols) != 1:
        raise ValueError("Run-summary persistence supports exactly one symbol per result")
    return symbols[0]


def _final_portfolio_snapshot(result: BacktestResult) -> PortfolioSnapshot:
    if not result.equity_curve:
        raise ValueError("Cannot persist a backtest result without a final portfolio snapshot")
    return result.equity_curve[-1]


def _final_open_exposure(
    *,
    result: BacktestResult,
    final_snapshot: PortfolioSnapshot,
) -> tuple[str | None, float]:
    request_symbols = [str(symbol) for symbol in result.request.symbols]
    for symbol in request_symbols:
        quantity = float(final_snapshot.positions.get(symbol, 0.0))
        if quantity != 0.0:
            return symbol, quantity

    open_positions = [
        (str(symbol), float(quantity))
        for symbol, quantity in final_snapshot.positions.items()
        if float(quantity) != 0.0
    ]
    if not open_positions:
        return None, 0.0
    if len(open_positions) == 1:
        return open_positions[0]
    raise ValueError("Run-summary persistence supports at most one final open position")


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


def _metric_float(result: BacktestResult, key: str) -> float:
    try:
        value = float(result.metrics[key])
    except KeyError as exc:
        raise ValueError(f"BacktestResult metrics missing required key: {key}") from exc
    if not math.isfinite(value):
        raise ValueError(f"BacktestResult metric must be finite: {key}")
    return value


def _metric_int(result: BacktestResult, key: str) -> int:
    value = _metric_float(result, key)
    return int(value)


def _metadata_from_response(response: Mapping[str, Any]) -> BacktestPersistenceMetadata:
    run_id = response.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("Backtest persistence response missing run_id")

    if "persisted_at" not in response:
        raise ValueError("Backtest persistence response missing persisted_at")

    return BacktestPersistenceMetadata(
        run_id=run_id,
        persisted_at=_persisted_at_to_epoch_ms(response["persisted_at"]),
    )


def _persisted_at_to_epoch_ms(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("persisted_at must be finite")
        return int(value)
    if isinstance(value, datetime):
        persisted_at = value
    elif isinstance(value, str):
        persisted_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("persisted_at must be an epoch millisecond value or datetime")

    if persisted_at.tzinfo is None:
        persisted_at = persisted_at.replace(tzinfo=timezone.utc)
    return int(persisted_at.timestamp() * 1000)


def _engine_value(engine: object) -> str:
    if isinstance(engine, BacktestEngine):
        return engine.value
    return str(engine)
