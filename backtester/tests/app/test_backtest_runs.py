from __future__ import annotations

import unittest
from dataclasses import replace

from app.backtest_runs import (
    BacktestRunNotFoundError,
    BacktestRunService,
    InvalidBacktestRequestError,
)
from domain.enums import (
    AllowedDirections,
    BacktestRunStatus,
    DataGranularity,
    ExitReason,
    OrderSide,
    PriceSource,
    TradeDirection,
)
from domain.types import (
    BacktestFillRecord,
    BacktestRequest,
    BacktestRunCancellation,
    BacktestRunQuery,
    BacktestRunRecord,
    BacktestTradeRecord,
    ExecutionConfig,
    StrategyConfig,
)


class _FakeRunRepository:
    def __init__(self) -> None:
        self.created_runs: list[BacktestRunRecord] = []
        self.runs_by_id: dict[str, BacktestRunRecord] = {}
        self.fills_by_run_id: dict[str, list[BacktestFillRecord]] = {}
        self.trades_by_run_id: dict[str, list[BacktestTradeRecord]] = {}
        self.deleted_run_ids: list[str] = []

    def create(self, run: BacktestRunRecord) -> BacktestRunRecord:
        self.created_runs.append(run)
        self.runs_by_id[run.run_id] = run
        return run

    def get(self, run_id: str) -> BacktestRunRecord | None:
        return self.runs_by_id.get(run_id)

    def rename(self, run_id: str, name: str | None) -> BacktestRunRecord:
        saved = replace(self.runs_by_id[run_id], name=name)
        self.runs_by_id[run_id] = saved
        return saved

    def cancel(self, run_id: str) -> BacktestRunCancellation:
        run = self.runs_by_id[run_id]
        cancelled = replace(
            run,
            status=BacktestRunStatus.CANCELLED,
            cancel_requested_at_ms=42,
            completed_at_ms=42,
            cancellation_source="user",
            cancellation_reason="user_requested",
        )
        self.runs_by_id[run_id] = cancelled
        return BacktestRunCancellation("accepted", cancelled)

    def list(self, query: BacktestRunQuery) -> list[BacktestRunRecord]:
        del query
        return list(self.runs_by_id.values())

    def get_fills(self, run_id: str) -> list[BacktestFillRecord]:
        return list(self.fills_by_run_id.get(run_id, []))

    def get_trades(self, run_id: str) -> list[BacktestTradeRecord]:
        return list(self.trades_by_run_id.get(run_id, []))

    def delete(self, run_id: str) -> bool:
        if run_id not in self.runs_by_id:
            return False
        self.deleted_run_ids.append(run_id)
        del self.runs_by_id[run_id]
        self.fills_by_run_id.pop(run_id, None)
        self.trades_by_run_id.pop(run_id, None)
        return True


class TestBacktestRunService(unittest.TestCase):
    def test_submit_accepts_allowed_direction_modes_before_persistence(self) -> None:
        for direction in AllowedDirections:
            with self.subTest(direction=direction.value):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)
                request = replace(
                    _valid_request(),
                    execution=ExecutionConfig(allowed_directions=direction),
                )

                submitted = _seed_run(service, request)

                self.assertEqual(
                    submitted.request_snapshot.to_request().execution, request.execution
                )
                self.assertEqual(
                    submitted.request_snapshot.payload["execution"]["allowed_directions"],
                    direction.value,
                )
                self.assertEqual(repository.created_runs, [submitted])

    def test_submit_rejects_invalid_timestamp_range_before_persistence(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(repository=repository)
        request = _valid_request()
        request = replace(request, start_ms=request.end_ms)

        with self.assertRaisesRegex(InvalidBacktestRequestError, "start_ms must be less"):
            _seed_run(service, request)

        self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_non_integer_timestamps_before_persistence(self) -> None:
        invalid_timestamps = (
            replace(_valid_request(), start_ms=True),
            replace(_valid_request(), end_ms=1_714_608_000_000.5),
        )

        for request in invalid_timestamps:
            with self.subTest(request=request):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(
                    InvalidBacktestRequestError,
                    "integer epoch milliseconds",
                ):
                    _seed_run(service, request)

                self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_non_single_symbol_or_non_bar_requests(self) -> None:
        invalid_requests = (
            (replace(_valid_request(), symbols=["EURUSD", "GBPUSD"]), "exactly one symbol"),
            (
                replace(_valid_request(), data_granularity=DataGranularity.TICK),
                "bar data only",
            ),
        )

        for request, message in invalid_requests:
            with self.subTest(message=message):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(InvalidBacktestRequestError, message):
                    _seed_run(service, request)

                self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_unknown_or_invalid_strategy_before_persistence(self) -> None:
        invalid_requests = (
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(strategy_id="unknown", strategy_version=1),
                ),
                "Unknown strategy_id",
            ),
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(
                        strategy_id="sma_crossover",
                        parameters={"fast_window": 20, "slow_window": 5},
                        strategy_version=1,
                    ),
                ),
                "Fast window must be smaller",
            ),
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(
                        strategy_id="sma_crossover",
                        parameters={"fast_window": 1.5, "slow_window": 20},
                        strategy_version=1,
                    ),
                ),
                "fast_window must be int",
            ),
        )

        for request, message in invalid_requests:
            with self.subTest(message=message):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(ValueError, message):
                    _seed_run(service, request)

                self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_unsupported_execution_policies_before_persistence(self) -> None:
        invalid_execution_configs = (
            replace(ExecutionConfig(), allow_partial_fills=True),
            replace(ExecutionConfig(), price_source=PriceSource.CLOSE),
        )

        for execution in invalid_execution_configs:
            with self.subTest(execution=execution):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(
                    InvalidBacktestRequestError,
                    "Unsupported execution configuration",
                ):
                    _seed_run(service, replace(_valid_request(), execution=execution))

                self.assertEqual(repository.created_runs, [])

    def test_get_returns_persisted_run_and_reports_missing_identity(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
        )
        submitted = _seed_run(service, _valid_request())

        self.assertEqual(service.get("run-1"), submitted)
        with self.assertRaisesRegex(BacktestRunNotFoundError, "run-missing"):
            service.get("run-missing")

    def test_get_execution_logs_requires_existing_run_and_preserves_order(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
        )
        queued = _seed_run(service, _valid_request())
        repository.runs_by_id["run-123"] = replace(
            queued,
            status=BacktestRunStatus.SUCCEEDED,
            started_at_ms=1_780_921_860_000,
            completed_at_ms=1_780_922_100_000,
            result_schema_version=3,
            metrics={"profit_factor": None, "trade_count": 1},
            diagnostics={"bars": 10},
        )
        fills = [
            BacktestFillRecord(
                run_id="run-123",
                sequence=0,
                timestamp_ms=1_714_525_200_000,
                symbol="EURUSD",
                side=OrderSide.BUY,
                quantity=1_000.0,
                price=1.0715,
                fees=0.15,
            ),
            BacktestFillRecord(
                run_id="run-123",
                sequence=1,
                timestamp_ms=1_714_532_400_000,
                symbol="EURUSD",
                side=OrderSide.SELL,
                quantity=1_000.0,
                price=1.074,
                fees=0.15,
                exit_reason=ExitReason.TAKE_PROFIT,
            ),
        ]
        trades = [
            BacktestTradeRecord(
                run_id="run-123",
                sequence=0,
                trade_id="trade-1",
                symbol="EURUSD",
                trade_direction=TradeDirection.LONG,
                quantity=1_000.0,
                entry_timestamp_ms=1_714_525_200_000,
                entry_price=1.0715,
                exit_timestamp_ms=1_714_532_400_000,
                exit_price=1.074,
                realized_pnl=2.5,
                fees=0.3,
                exit_reason=ExitReason.TAKE_PROFIT,
                stop_loss_price=1.05,
                take_profit_price=1.08,
            )
        ]
        repository.fills_by_run_id["run-123"] = fills
        repository.trades_by_run_id["run-123"] = trades

        self.assertEqual(service.get_fills("run-123"), fills)
        self.assertEqual(service.get_trades("run-123"), trades)
        with self.assertRaisesRegex(BacktestRunNotFoundError, "run-missing"):
            service.get_fills("run-missing")
        with self.assertRaisesRegex(BacktestRunNotFoundError, "run-missing"):
            service.get_trades("run-missing")


def _valid_request() -> BacktestRequest:
    return BacktestRequest(
        symbols=["EURUSD"],
        exchange="FX",
        timeframe="M15",
        start_ms=1_714_521_600_000,
        end_ms=1_714_608_000_000,
        strategy=StrategyConfig(
            strategy_id="sma_crossover",
            parameters={
                "fast_window": 5,
                "slow_window": 20,
                "quantity": 1_000.0,
            },
            strategy_version=1,
        ),
        execution=ExecutionConfig(),
        initial_capital=25_000.0,
    )


if __name__ == "__main__":
    unittest.main()


def _seed_run(service: BacktestRunService, request: BacktestRequest):
    from typing import cast

    from app.backtest_runs import _validate_submission
    from domain.enums import BacktestRunStatus
    from domain.types import BacktestRequestSnapshot, BacktestRunRecord

    run = BacktestRunRecord(
        run_id="run-1",
        backtest_id="backtest-1",
        run_ordinal=0,
        status=BacktestRunStatus.QUEUED,
        submitted_at_ms=1000,
        request_snapshot=BacktestRequestSnapshot.from_request(_validate_submission(request)),
    )
    return cast(_FakeRunRepository, service._repository).create(run)
