from __future__ import annotations

import unittest
from dataclasses import replace

from app.backtest_runs import (
    BacktestRunConflictError,
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
)
from domain.types import (
    BacktestFillRecord,
    BacktestRequest,
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
    def test_submit_persists_immutable_queued_run(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-123",
            now_ms=lambda: 1_780_921_805_123,
        )
        request = _valid_request()

        submitted = service.submit(request)

        self.assertEqual(submitted.run_id, "run-123")
        self.assertEqual(submitted.status, BacktestRunStatus.QUEUED)
        self.assertEqual(submitted.submitted_at_ms, 1_780_921_805_123)
        self.assertEqual(submitted.request_snapshot.to_request(), request)
        self.assertEqual(submitted.request_snapshot.schema_version, 2)
        self.assertEqual(
            submitted.request_snapshot.payload["execution"]["allowed_directions"],
            "long_and_short",
        )
        self.assertNotIn("allow_short", submitted.request_snapshot.payload["execution"])
        self.assertEqual(repository.created_runs, [submitted])

    def test_submit_accepts_allowed_direction_modes_before_persistence(self) -> None:
        for direction in AllowedDirections:
            with self.subTest(direction=direction.value):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)
                request = replace(
                    _valid_request(),
                    execution=ExecutionConfig(allowed_directions=direction),
                )

                submitted = service.submit(request)

                self.assertEqual(submitted.request_snapshot.to_request(), request)
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
            service.submit(request)

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
                    service.submit(request)

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
                    service.submit(request)

                self.assertEqual(repository.created_runs, [])

    def test_submit_rejects_unknown_or_invalid_strategy_before_persistence(self) -> None:
        invalid_requests = (
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(strategy_id="unknown"),
                ),
                "Unknown strategy_id",
            ),
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(
                        strategy_id="sma_crossover",
                        parameters={"fast_window": 20, "slow_window": 5},
                    ),
                ),
                "fast_window must be strictly smaller",
            ),
            (
                replace(
                    _valid_request(),
                    strategy=StrategyConfig(
                        strategy_id="sma_crossover",
                        parameters={"fast_window": 1.5, "slow_window": 20},
                    ),
                ),
                "SMA windows must be integers",
            ),
        )

        for request, message in invalid_requests:
            with self.subTest(message=message):
                repository = _FakeRunRepository()
                service = BacktestRunService(repository=repository)

                with self.assertRaisesRegex(InvalidBacktestRequestError, message):
                    service.submit(request)

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
                    service.submit(replace(_valid_request(), execution=execution))

                self.assertEqual(repository.created_runs, [])

    def test_get_returns_persisted_run_and_reports_missing_identity(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-123",
            now_ms=lambda: 1_780_921_805_123,
        )
        submitted = service.submit(_valid_request())

        self.assertEqual(service.get("run-123"), submitted)
        with self.assertRaisesRegex(BacktestRunNotFoundError, "run-missing"):
            service.get("run-missing")

    def test_get_execution_logs_requires_existing_run_and_preserves_order(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-123",
            now_ms=lambda: 1_780_921_805_123,
        )
        queued = service.submit(_valid_request())
        repository.runs_by_id["run-123"] = replace(
            queued,
            status=BacktestRunStatus.SUCCEEDED,
            started_at_ms=1_780_921_860_000,
            completed_at_ms=1_780_922_100_000,
            result_schema_version=2,
            metrics={"trade_count": 1},
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

    def test_delete_allows_terminal_runs_and_rejects_active_runs(self) -> None:
        repository = _FakeRunRepository()
        service = BacktestRunService(
            repository=repository,
            new_run_id=lambda: "run-base",
            now_ms=lambda: 1_780_921_805_123,
        )
        queued = service.submit(_valid_request())
        repository.runs_by_id = {
            "run-queued": replace(queued, run_id="run-queued"),
            "run-running": replace(
                queued,
                run_id="run-running",
                status=BacktestRunStatus.RUNNING,
            ),
            "run-succeeded": replace(
                queued,
                run_id="run-succeeded",
                status=BacktestRunStatus.SUCCEEDED,
            ),
            "run-failed": replace(
                queued,
                run_id="run-failed",
                status=BacktestRunStatus.FAILED,
            ),
        }

        service.delete("run-succeeded")
        service.delete("run-failed")

        self.assertEqual(repository.deleted_run_ids, ["run-succeeded", "run-failed"])
        for run_id in ("run-queued", "run-running"):
            with self.subTest(run_id=run_id):
                with self.assertRaisesRegex(BacktestRunConflictError, "terminal"):
                    service.delete(run_id)
                self.assertIn(run_id, repository.runs_by_id)

        with self.assertRaisesRegex(BacktestRunNotFoundError, "run-missing"):
            service.delete("run-missing")


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
        ),
        execution=ExecutionConfig(),
        initial_capital=25_000.0,
    )


if __name__ == "__main__":
    unittest.main()
